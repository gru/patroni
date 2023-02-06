docker-compose -f ./docker-compose.yml exec schema_registry kafka-avro-console-consumer \
    --bootstrap-server kafka:9092 \
    --from-beginning \
    --property print.key=true \
    --topic $1