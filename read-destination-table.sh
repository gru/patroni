docker-compose -f ./docker-compose.yml exec destination /bin/sh -c '\
    psql -U postgres -d destination_db -c \
	"select * from public.debezium_table;"'