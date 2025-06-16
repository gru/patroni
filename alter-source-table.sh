docker-compose -f ./docker-compose.yml exec haproxy /bin/sh -c '\
	export PGPORT=5000 && \
	export PGHOST=haproxy && \
    psql -U postgres -d source_db -c \
	"ALTER TABLE public.debezium_table add column extra1 int null default 10;"'