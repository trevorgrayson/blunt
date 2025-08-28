from ics import Calendar
from http.client import HTTPSConnection
from argparse import ArgumentParser
from urllib.parse import urlparse

parser = ArgumentParser("display ics calendar")
parser.add_argument("url", help="calendar url")
args = parser.parse_args()

asset = urlparse(args.url)

conn = HTTPSConnection(asset.hostname)
conn.request("GET", asset.path + "?" + asset.query)
# result = conn.urlopen('GET', url=args.url)
resp = conn.getresponse()
if resp.status != 200:
    raise Exception(str(resp.status) + resp.read().decode("utf8"))

result = resp.read().decode("utf8")
c = Calendar(result)
# for event in c.events:
#     print(event)

for e in c.timeline:
    print(e.name, e.begin.humanize(), e.begin.date(), "->", e.end.date().day)
