docker-compose -f ./docker-compose.yml exec destination /bin/sh -c '\
    psql -U postgres -d destination_db -c \
	"ALTER TABLE public.debezium_table add column extra1 int null;"'