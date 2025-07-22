from . import Confluent, Metrics
import json
client = Confluent()

results = client.received_bytes()

sum_ = 0
for result in results:
    sum_ += result.value

def bytes_to_mb(bytes_value):
    """
    Convert bytes to megabytes (MB), accurate to 3 decimal places.

    Parameters:
    - bytes_value (int or float): The number of bytes to convert.

    Returns:
    - float: The size in megabytes rounded to 3 decimal places.
    """
    if not isinstance(bytes_value, (int, float)):
        raise TypeError("Input must be an integer or float representing bytes.")

    mb_value = bytes_value / 1_000_000
    return round(mb_value, 3)

# print(json.dumps(client.top_topics()))

print(json.dumps(client.query(Metrics.TopTopics, "metric.topic")))
exit(0)
# print(sum_)
import plotille

n = range(0, len(results))
# 1hr => seconds
values = [bytes_to_mb(result.value/(60)) for result in results]

fig = plotille.Figure()
print(plotille.plot(n, values, height=30, width=60, interp="linear", lc="cyan", Y_label="MB/s", X_label="time"))

print(results[-1])
