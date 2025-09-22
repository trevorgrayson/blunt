from argparse import ArgumentParser
from . import Confluent, bytes_to_mb

parser = ArgumentParser()
parser.add_argument("--format", "-f", default="statsd")
args = parser.parse_args()

client = Confluent()
results = client.received_bytes()


n = range(0, len(results))
# 1hr => seconds
values = [bytes_to_mb(result.value/(60)) for result in results]

if args.format == 'statsd':
    print(f"bytes_received:{values[-1]}|g")

elif args.format.startswith('g'):
    import plotille
    fig = plotille.Figure()
    print(plotille.plot(n, values, height=30, width=60, interp="linear", lc="cyan", Y_label="MB/s", X_label="time"))
    
else:
    print(values)
