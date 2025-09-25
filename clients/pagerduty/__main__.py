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
parser.add_argument("--active", "-a", action="store_true",
                    help="Only active incidents (triggered, acknowledged)")
parser.add_argument("--urgency", "-u",
                    help="urgency: high, or low")
parser.add_argument("--format", "-f",
                    help="default or statsd")
args = parser.parse_args()

days_ago = datetime.now() - timedelta(days=args.days)

client = PagerDuty(TOKEN)

params = dict(
    since=days_ago.date(),
    limit=args.limit,
    offset=args.offset
)
if args.team:
    params["team_ids"] = [args.team]
if args.active:
    params["statuses"] = ["triggered", "acknowledged"]
if args.urgency:
    params["urgencies"] = [args.urgency]

count = 0
incs = client.incidents(**params) # statuses=["resolved"],

if args.format == "statsd":
    print(f"pagerduty.incidents.count:{len(incs)}|g")
    # for inc in incs:
    #     created_at = datetime.fromisoformat(inc.created_at.rstrip("Z"))
    #     age_hours = (datetime.now() - created_at).total_seconds() / 3600
    #     print(f"pagerduty.incident.age_hours:{age_hours}|g")
    #     if inc.status == "acknowledged":
    #         acked_at = datetime.fromisoformat(inc.acknowledged_at.rstrip("Z"))
    #         ack_age_hours = (datetime.now() - acked_at).total_seconds() / 3600
    #         print(f"pagerduty.incident.ack_age_hours:{ack_age_hours}|g")
    #     elif inc.status == "resolved":
    #         resolved_at = datetime.fromisoformat(inc.resolved_at.rstrip("Z"))
    #         res_age_hours = (datetime.now() - resolved_at).total_seconds() / 3600
    #         print(f"pagerduty.incident.res_age_hours:{res_age_hours}|g")
    exit(0)

for inc in incs:
    count += 1
    print(inc)

if args.count:
    print(f"count: {count}")
