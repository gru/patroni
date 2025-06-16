docker-compose -f ./docker-compose.yml exec kafka /kafka/bin/kafka-topics.sh --list \
    --bootstrap-server kafka:9092