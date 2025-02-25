from kafka import KafkaProducer

# Create a Kafka producer
producer = KafkaProducer(bootstrap_servers='localhost:9092')

# Send messages to the topic
for i in range(10):
    message = f"Message {i}".encode('utf-8')
    producer.send('test-topic', message)
    print(f"Sent: {message}")

# Close the producer
producer.close()
