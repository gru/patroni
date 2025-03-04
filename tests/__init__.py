import datetime
import os
import shutil
import unittest

from mock import Mock, patch

import urllib3

import patroni.psycopg as psycopg

from patroni.dcs import Leader, Member
from patroni.postgresql import Postgresql
from patroni.postgresql.config import ConfigHandler
from patroni.utils import RetryFailedError, tzutc


class SleepException(Exception):
    pass


class MockResponse(object):

    def __init__(self, status_code=200):
        self.status_code = status_code
        self.content = '{}'
        self.reason = 'Not Found'

    @property
    def data(self):
        return self.content.encode('utf-8')

    @property
    def status(self):
        return self.status_code

    @staticmethod
    def getheader(*args):
        return ''

    @staticmethod
    def getheaders():
        return {'content-type': 'json'}


def requests_get(url, method='GET', endpoint=None, data='', **kwargs):
    members = '[{"id":14855829450254237642,"peerURLs":["http://localhost:2380","http://localhost:7001"],' +\
              '"name":"default","clientURLs":["http://localhost:2379","http://localhost:4001"]}]'
    response = MockResponse()
    if endpoint == 'failsafe':
        response.content = 'Accepted'
    elif url.startswith('http://local'):
        raise urllib3.exceptions.HTTPError()
    elif ':8011/patroni' in url:
        response.content = '{"role": "replica", "wal": {"received_location": 0}, "tags": {}}'
    elif url.endswith('/members'):
        response.content = '[{}]' if url.startswith('http://error') else members
    elif url.startswith('http://exhibitor'):
        response.content = '{"servers":["127.0.0.1","127.0.0.2","127.0.0.3"],"port":2181}'
    elif url.endswith(':8011/reinitialize'):
        if ' false}' in data:
            response.status_code = 503
            response.content = 'restarting after failure already in progress'
    else:
        response.status_code = 404
    return response


class MockPostmaster(object):
    def __init__(self, is_running=True, is_single_master=False):
        self.is_running = Mock(return_value=is_running)
        self.is_single_master = Mock(return_value=is_single_master)
        self.wait_for_user_backends_to_close = Mock()
        self.signal_stop = Mock(return_value=None)
        self.wait = Mock()
        self.signal_kill = Mock(return_value=False)


class MockCursor(object):

    def __init__(self, connection):
        self.connection = connection
        self.closed = False
        self.rowcount = 0
        self.results = []
        self.description = [Mock()]

    def execute(self, sql, *params):
        if sql.startswith('blabla'):
            raise psycopg.ProgrammingError()
        elif sql == 'CHECKPOINT' or sql.startswith('SELECT pg_catalog.pg_create_'):
            raise psycopg.OperationalError()
        elif sql.startswith('RetryFailedError'):
            raise RetryFailedError('retry')
        elif sql.startswith('SELECT slot_name, catalog_xmin'):
            self.results = [('postgresql0', 100), ('ls', 100)]
        elif sql.startswith('SELECT slot_name, slot_type, datname, plugin, catalog_xmin'):
            self.results = [('ls', 'logical', 'a', 'b', 100, 500, b'123456')]
        elif sql.startswith('SELECT slot_name'):
            self.results = [('blabla', 'physical'), ('foobar', 'physical'), ('ls', 'logical', 'a', 'b', 5, 100, 500)]
        elif sql.startswith('SELECT CASE WHEN pg_catalog.pg_is_in_recovery()'):
            self.results = [(1, 2, 1, 0, False, 1, 1, None, None, [{"slot_name": "ls", "confirmed_flush_lsn": 12345}])]
        elif sql.startswith('SELECT pg_catalog.pg_is_in_recovery()'):
            self.results = [(False, 2)]
        elif sql.startswith('SELECT pg_catalog.pg_postmaster_start_time'):
            replication_info = '[{"application_name":"walreceiver","client_addr":"1.2.3.4",' +\
                               '"state":"streaming","sync_state":"async","sync_priority":0}]'
            now = datetime.datetime.now(tzutc)
            self.results = [(now, 0, '', 0, '', False, now, replication_info)]
        elif sql.startswith('SELECT name, setting'):
            self.results = [('wal_segment_size', '2048', '8kB', 'integer', 'internal'),
                            ('wal_block_size', '8192', None, 'integer', 'internal'),
                            ('shared_buffers', '16384', '8kB', 'integer', 'postmaster'),
                            ('wal_buffers', '-1', '8kB', 'integer', 'postmaster'),
                            ('search_path', 'public', None, 'string', 'user'),
                            ('port', '5433', None, 'integer', 'postmaster'),
                            ('listen_addresses', '*', None, 'string', 'postmaster'),
                            ('autovacuum', 'on', None, 'bool', 'sighup'),
                            ('unix_socket_directories', '/tmp', None, 'string', 'postmaster')]
        elif sql.startswith('IDENTIFY_SYSTEM'):
            self.results = [('1', 3, '0/402EEC0', '')]
        elif sql.startswith('TIMELINE_HISTORY '):
            self.results = [('', b'x\t0/40159C0\tno recovery target specified\n\n'
                                 b'1\t0/40159C0\tno recovery target specified\n\n'
                                 b'2\t0/402DD98\tno recovery target specified\n\n'
                                 b'3\t0/403DD98\tno recovery target specified\n')]
        else:
            self.results = [(None, None, None, None, None, None, None, None, None, None)]

    def fetchone(self):
        return self.results[0]

    def fetchall(self):
        return self.results

    def __iter__(self):
        for i in self.results:
            yield i

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class MockConnect(object):

    server_version = 99999
    autocommit = False
    closed = 0

    def cursor(self):
        return MockCursor(self)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    @staticmethod
    def close():
        pass


def psycopg_connect(*args, **kwargs):
    return MockConnect()


class PostgresInit(unittest.TestCase):
    _PARAMETERS = {'wal_level': 'hot_standby', 'max_replication_slots': 5, 'f.oo': 'bar',
                   'search_path': 'public', 'hot_standby': 'on', 'max_wal_senders': 5,
                   'wal_keep_segments': 8, 'wal_log_hints': 'on', 'max_locks_per_transaction': 64,
                   'max_worker_processes': 8, 'max_connections': 100, 'max_prepared_transactions': 0,
                   'track_commit_timestamp': 'off', 'unix_socket_directories': '/tmp',
                   'trigger_file': 'bla', 'stats_temp_directory': '/tmp', 'zero_damaged_pages': '',
                   'force_parallel_mode': '1', 'constraint_exclusion': '',
                   'max_stack_depth': 'Z', 'vacuum_cost_limit': -1, 'vacuum_cost_delay': 200}

    @patch('patroni.psycopg._connect', psycopg_connect)
    @patch('patroni.postgresql.CallbackExecutor', Mock())
    @patch.object(ConfigHandler, 'write_postgresql_conf', Mock())
    @patch.object(ConfigHandler, 'replace_pg_hba', Mock())
    @patch.object(ConfigHandler, 'replace_pg_ident', Mock())
    @patch.object(Postgresql, 'get_postgres_role_from_data_directory', Mock(return_value='master'))
    def setUp(self):
        data_dir = os.path.join('data', 'test0')
        self.p = Postgresql({'name': 'postgresql0', 'scope': 'batman', 'data_dir': data_dir,
                             'config_dir': data_dir, 'retry_timeout': 10,
                             'krbsrvname': 'postgres', 'pgpass': os.path.join(data_dir, 'pgpass0'),
                             'listen': '127.0.0.2, 127.0.0.3:5432',
                             'connect_address': '127.0.0.2:5432', 'proxy_address': '127.0.0.2:5433',
                             'authentication': {'superuser': {'username': 'foo', 'password': 'test'},
                                                'replication': {'username': '', 'password': 'rep-pass'},
                                                'rewind': {'username': 'rewind', 'password': 'test'}},
                             'remove_data_directory_on_rewind_failure': True,
                             'use_pg_rewind': True, 'pg_ctl_timeout': 'bla',
                             'parameters': self._PARAMETERS,
                             'recovery_conf': {'foo': 'bar'},
                             'pg_hba': ['host all all 0.0.0.0/0 md5'],
                             'pg_ident': ['krb realm postgres'],
                             'callbacks': {'on_start': 'true', 'on_stop': 'true', 'on_reload': 'true',
                                           'on_restart': 'true', 'on_role_change': 'true'}})


class BaseTestPostgresql(PostgresInit):

    def setUp(self):
        super(BaseTestPostgresql, self).setUp()

        if not os.path.exists(self.p.data_dir):
            os.makedirs(self.p.data_dir)

        self.leadermem = Member(0, 'leader', 28, {
            'state': 'running', 'conn_url': 'postgres://replicator:rep-pass@127.0.0.1:5435/postgres'})
        self.leader = Leader(-1, 28, self.leadermem)
        self.other = Member(0, 'test-1', 28, {'conn_url': 'postgres://replicator:rep-pass@127.0.0.1:5433/postgres',
                                              'state': 'running', 'tags': {'replicatefrom': 'leader'}})
        self.me = Member(0, 'test0', 28, {
            'state': 'running', 'conn_url': 'postgres://replicator:rep-pass@127.0.0.1:5434/postgres'})

    def tearDown(self):
        if os.path.exists(self.p.data_dir):
            shutil.rmtree(self.p.data_dir)
