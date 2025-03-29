from os import environ
from . import PagerDuty

TOKEN = environ.get("PAGERDUTY_TOKEN")

client = PagerDuty(TOKEN)

incs = client.incidents(statuses=["resolved"]) # since="2025-01-01")
for inc in incs:
    print(inc)