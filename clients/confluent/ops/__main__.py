from argparse import ArgumentParser
import time
from confluent_kafka import Consumer, TopicPartition

parser = ArgumentParser("topic offset adjusting, 'reset'")
parser.add_argument("--bootstrap",
                    help="bootstrap server [hostname:9092]")
parser.add_argument("group", type=int, help="consumer_group to reset")
parser.add_argument("topic", help="topic name")
parser.add_argument("timestamp", type=int, help="offset timestamp [2025-09-01 00:00:00]")
args = parser.parse_args()

# Configuration for Kafka
conf = {
    'bootstrap.servers': args.bootstrap,   # Kafka broker(s)
    'group.id': args.group,         # Consumer group to reset
    # 'auto.offset.reset': 'earliest',         # fallback if timestamp not found
}

# Parameters
timestamp_ms = int(time.mktime(time.strptime(args.timestamp, "%Y-%m-%d %H:%M:%S"))) * 1000

consumer = Consumer(conf)

# Get partitions for the topic
partitions = consumer.list_topics(args.topic).topics[args.topic].partitions
topic_partitions = [TopicPartition(args.topic, p, timestamp_ms) for p in partitions]

# Look up offsets for given timestamps
offsets_for_times = consumer.offsets_for_times(topic_partitions, timeout=10.0)

# Assign partitions with the resolved offsets
for tp in offsets_for_times:
    if tp.offset != -1:
        print(f"Resetting partition {tp.partition} to offset {tp.offset} for timestamp {timestamp_ms}")
        consumer.assign([tp])
    else:
        print(f"No offset found for partition {tp.partition} at timestamp {timestamp_ms}, skipping.")

# Commit offsets to the consumer group
consumer.commit(asynchronous=False)

consumer.close()
