from os import environ
from argparse import ArgumentParser
from datetime import datetime, timedelta
from . import PagerDuty


TOKEN = environ.get("PAGERDUTY_TOKEN")


parser = ArgumentParser(description="PagerDuty API Client")
parser.add_argument("--days", default=7, type=int,
                    help="Number of days to query (default: %(default)s)")
parser.add_argument("--count", action='store_true')
parser.add_argument("--limit", type=int, default=100)
parser.add_argument("--offset", type=int, default=0)
parser.add_argument("--team", default=None,
                    help="Team ID")
args = parser.parse_args()

days_ago = datetime.now() - timedelta(days=args.days)

client = PagerDuty(TOKEN)

params = dict(
    since=days_ago.date(),
    limit=args.limit,
    offset=args.offset
)
if args.team:
    params["team_ids[]"] = args.team

count = 0
incs = client.incidents(**params) # statuses=["resolved"],
for inc in incs:
    count += 1
    print(inc)

if args.count:
    print(f"count: {count}")
