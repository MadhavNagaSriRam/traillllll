from kafka import KafkaConsumer

# Create a Kafka consumer
consumer = KafkaConsumer(
    'test-topic',
    bootstrap_servers='localhost:9092',
    auto_offset_reset='earliest',  # Start from the earliest message
    group_id='my-group'
)

# Read and print messages
for message in consumer:
    print(f"Received: {message.value.decode('utf-8')}")
