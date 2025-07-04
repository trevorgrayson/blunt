from argparse import ArgumentParser
from . import Confluent

METRICS = [
    "consumer_lag",
    "received_bytes",
    "sent_bytes",
    # "producer_latency_avg_milliseconds"
]
parser = ArgumentParser(description="Confluent Cluster Metrics")
parser.add_argument("metric", choices=METRICS, default="received_bytes",
                    help="Metric name.")
args = parser.parse_args()

client = Confluent()
results = client.received_bytes()

for result in results:
    print(result)

sum_ = 0
for result in results:
    sum_ += result.value

print(sum_)