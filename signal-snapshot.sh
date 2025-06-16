docker-compose -f ./docker-compose.yml exec haproxy /bin/sh -c $'\
	export PGPORT=5000 && \
	export PGHOST=haproxy && \
	psql -U postgres -d source_db -f /home/postgres/signal-snapshot.sql'