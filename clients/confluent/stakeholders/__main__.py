#!/usr/bin/env python3
"""
List consumer groups (and their members) that are consuming a given topic
via Confluent Kafka REST API v3.

Required env vars:
  REST_ENDPOINT   e.g. https://pkc-xxxxx.us-west4.gcp.confluent.cloud:443
  CLUSTER_ID      e.g. lkc-abc123
  API_KEY         Confluent (Kafka REST) API key
  API_SECRET      Confluent (Kafka REST) API secret
  TOPIC           Topic name to check

References:
- List groups / lags / consumers (v3): /kafka/v3/clusters/{cluster_id}/consumer-groups, /lags, /consumers
"""

import os
import json
import base64
import urllib.request
import urllib.parse
from typing import Dict, Any, List

REST_ENDPOINT = os.environ.get("KAFKA_REST_ENDPOINT")
CLUSTER_ID    = os.environ.get("KAFKA_ID")
API_KEY       = os.environ.get("KAFKA_API_KEY")
API_SECRET    = os.environ.get("KAFKA_API_SECRET")
TOPIC         = os.environ.get("TOPIC")

if not all([REST_ENDPOINT, CLUSTER_ID, API_KEY, API_SECRET, TOPIC]):
    raise SystemExit("Missing one or more required env vars: KAFKA_REST_ENDPOINT, KAFKA_CLUSTER_ID, KAFKA_API_KEY, KAFKA_API_SECRET, TOPIC")

BASE = REST_ENDPOINT.rstrip("/") + f"/kafka/v3/clusters/{CLUSTER_ID}"

basic = base64.b64encode(f"{API_KEY}:{API_SECRET}".encode("utf-8")).decode("ascii")
HDRS = {
    "Accept": "application/json",
    "Authorization": f"Basic {basic}",
    "Connection": "close",
    "User-Agent": "topic-consumers/1.0",
}

def fetch_json(url: str) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers=HDRS, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
    return json.loads(data.decode("utf-8"))

def paginate(first_url: str) -> List[Dict[str, Any]]:
    """Follow REST v3 pagination using metadata.next links; return aggregated 'data' items."""
    items: List[Dict[str, Any]] = []
    url = first_url
    while url:
        doc = fetch_json(url)
        if isinstance(doc, dict) and "data" in doc:
            items.extend(doc["data"])
        # v3 lists usually carry 'metadata.next' for pagination
        next_url = None
        meta = doc.get("metadata") if isinstance(doc, dict) else None
        if isinstance(meta, dict):
            next_url = meta.get("next")
        url = next_url
    return items

def list_consumer_groups() -> List[str]:
    url = BASE + "/consumer-groups"
    items = paginate(url)
    gids = [i.get("consumer_group_id") for i in items if "consumer_group_id" in i]
    return [g for g in gids if g]  # non-empty

def group_lags(group_id: str) -> List[Dict[str, Any]]:
    # Returns per-partition lag entries with 'topic_name', 'lag', etc.
    url = BASE + f"/consumer-groups/{urllib.parse.quote(group_id, safe='')}/lags"
    return paginate(url)

def group_consumers(group_id: str) -> List[Dict[str, Any]]:
    # Returns consumers (members) in the group with consumer_id, client_id, instance_id
    url = BASE + f"/consumer-groups/{urllib.parse.quote(group_id, safe='')}/consumers"
    return paginate(url)

def main() -> None:
    groups = list_consumer_groups()
    results = []

    for gid in groups:
        lags = group_lags(gid)
        topic_lags = [entry for entry in lags if entry.get("topic_name") == TOPIC]
        if not topic_lags:
            continue  # this group isn't consuming the topic

        total_lag = sum(int(entry.get("lag", 0) or 0) for entry in topic_lags)
        members_docs = group_consumers(gid)  # may be empty if no active members
        members = []
        for m in members_docs:
            members.append({
                "consumer_id": m.get("consumer_id"),
                "client_id": m.get("client_id"),
                "instance_id": m.get("instance_id"),
            })

        results.append({
            "consumer_group": gid,
            "total_lag_for_topic": total_lag,
            "partition_count_for_topic": len({(e.get("topic_name"), e.get("partition_id")) for e in topic_lags}),
            "members": members,
        })

    print(json.dumps({
        "topic": TOPIC,
        "cluster_id": CLUSTER_ID,
        "consumer_groups_count": len(results),
        "consumer_groups": sorted(results, key=lambda r: r["consumer_group"]),
    }, indent=2))

if __name__ == "__main__":
    main()
