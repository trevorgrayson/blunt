#!/usr/bin/env python3
"""
Quick script to fetch bytes produced/consumed and cluster load / CPU
from Confluent Cloud Metrics API using only Python stdlib.

Usage:
    python confluent_metrics.py --api-key ABC --api-secret XYZ [--cluster-id lkc-...] [--minutes 5]

Notes:
 - The API key must be a "Cloud" (resource-management) API key with MetricsViewer role.
 - Metrics are retained for ~7 days in the Metrics API; adjust intervals as needed.
"""
from os import environ
import argparse
import base64
import datetime
import json
import sys
import urllib.parse
import urllib.request
from typing import Optional, Dict, Any, List

API_KEY = environ["CONFLUENT_API_KEY"]
API_SECRET = environ["CONFLUENT_API_SECRET"]
BASE = "https://api.telemetry.confluent.cloud/v2/metrics/cloud"

def basic_auth_header(api_key=API_KEY, api_secret=API_SECRET) -> Dict[str, str]:
    raw = f"{api_key}:{api_secret}".encode("utf-8")
    b64 = base64.b64encode(raw).decode("ascii")
    return {"Authorization": f"Basic {b64}", "Content-Type": "application/json"}


def http_get(url: str, headers: Dict[str, str]) -> Any:
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_post(url: str, headers: Dict[str, str], body: Dict[str, Any]) -> Any:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, headers=headers, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def discover_first_kafka_cluster(headers: Dict[str, str]) -> Optional[str]:
    """
    Call /descriptors/resources and find the first resource of type kafka.
    Returns resource id like lkc-XXXXX or None.
    """
    url = f"{BASE}/descriptors/resources"
    payload = http_get(url, headers)  # endpoint accepts basic GET with basic auth
    # payload is a map with items describing resources; we'll search for resource_type == "kafka"
    # defensive navigation:
    items = payload.get("resources") or payload.get("items") or payload
    # try different shapes:
    if isinstance(items, dict):
        # sometimes it's a mapping of resource_name -> descriptor
        for k, v in items.items():
            if isinstance(v, dict) and v.get("resource_type") == "kafka":
                return v.get("id") or v.get("resource_id") or k
    elif isinstance(items, list):
        for it in items:
            if it.get("resource_type") == "kafka":
                return it.get("id") or it.get("resource_id")
    # fallback: try to parse top-level if it already looks like a single resource object
    if isinstance(payload, dict) and payload.get("resource_type") == "kafka":
        return payload.get("id")
    return None


def make_iso_interval(minutes: int) -> List[str]:
    """
    Return an intervals list for Metrics API: start/end in ISO8601 UTC
    Example: ["2026-02-21T14:00:00Z/2026-02-21T14:05:00Z"]
    """
    now = datetime.datetime.utcnow().replace(microsecond=0)
    start = now - datetime.timedelta(minutes=minutes)
    # Metrics API examples use "Z" for UTC
    return [f"{start.isoformat()}Z/{now.isoformat()}Z"]


def query_metric(headers: Dict[str, str], metric_name: str, resource_field: str,
                 resource_id: str, group_by: Optional[List[str]], granularity: str,
                 minutes: int = 5, limit: Optional[int] = None) -> Dict[str, Any]:
    """
    Generic query helper that posts to /query.
    - metric_name: e.g. "io.confluent.kafka.server/received_bytes"
    - resource_field: e.g. "resource.kafka.id"
    - resource_id: e.g. "lkc-XXXXX"
    - group_by: list of labels like ["metric.topic"]
    - granularity: ISO8601 duration string like "PT1M" or "PT1H"
    """
    body = {
        "aggregations": [{"metric": metric_name}],
        "filter": {"field": resource_field, "op": "EQ", "value": resource_id},
        "granularity": granularity,
        "intervals": make_iso_interval(minutes),
    }
    if group_by:
        body["group_by"] = group_by
    if limit:
        body["limit"] = limit

    url = f"{BASE}/query"
    return http_post(url, headers, body)


def sum_series(series: List[Dict[str, Any]]) -> float:
    """Sum values in a list of datapoints where each datapoint has 'value'"""
    total = 0.0
    for p in series:
        try:
            total += float(p.get("value", 0.0))
        except Exception:
            pass
    return total


def normalize_and_print_timeseries(data: Dict[str, Any], metric_label: str):
    """
    The query response may vary in shape; try to find datapoints and print timestamps + values.
    Typical small example shape in docs: {"data":[{"timestamp": "...", "value": 72.0, ...}, ...]}
    """
    items = data.get("data") or data.get("result") or []
    if not items:
        print(f"No data returned for {metric_label}")
        return 0.0
    # If response contains nested objects (e.g. grouped results), try to flatten
    # If data is a list of points, sum their 'value'
    if isinstance(items, list) and items and isinstance(items[0], dict) and "timestamp" in items[0]:
        total = sum_series(items)
        print(f"\n{metric_label} timeseries ({len(items)} points):")
        for pt in items:
            ts = pt.get("timestamp")
            val = pt.get("value")
            print(f"  {ts}  -> {val}")
        print(f"Total {metric_label} over interval: {total}")
        return total
    # If grouped results: items may be list of dicts each with 'data' key
    total = 0.0
    for group in items:
        inner = group.get("data") or []
        subtotal = sum_series(inner)
        total += subtotal
        group_tags = {k: v for k, v in group.items() if k != "data"}
        print(f"\nGroup {group_tags} subtotal {metric_label}: {subtotal} (points: {len(inner)})")
    print(f"\nGrand total {metric_label}: {total}")
    return total


def main():
    p = argparse.ArgumentParser()
    # p.add_argument("--api-key", required=True)
    # p.add_argument("--api-secret", required=True)
    p.add_argument("--cluster-id", required=False, help="lkc-... (if omitted the script will try to discover one)")
    p.add_argument("--minutes", type=int, default=5, help="lookback window in minutes")
    p.add_argument("--observation", help="present values only")
    args = p.parse_args()

    headers = basic_auth_header()

    cluster_id = args.cluster_id
    if not cluster_id:
        print("No cluster id provided — discovering first kafka resource via descriptors/resources ...")
        try:
            cluster_id = discover_first_kafka_cluster(headers)
        except Exception as e:
            print("Failed to discover cluster id:", e, file=sys.stderr)
            sys.exit(1)
        if not cluster_id:
            print("Could not find a kafka cluster resource. Provide --cluster-id manually.", file=sys.stderr)
            sys.exit(1)
        print("Discovered cluster id:", cluster_id)

    minutes = args.minutes

    # --- bytes produced (ingress) per topic ---
    print("\nQuerying bytes produced (metric: io.confluent.kafka.server/received_bytes) ...")
    try:
        produced = query_metric(
            headers=headers,
            metric_name="io.confluent.kafka.server/received_bytes",
            resource_field="resource.kafka.id",
            resource_id=cluster_id,
            group_by=["metric.topic"],
            granularity="PT1M",
            minutes=minutes,
            limit=200
        )
        produced_total = normalize_and_print_timeseries(produced, "bytes_produced (received_bytes)")
    except Exception as e:
        print("Error querying bytes produced:", e, file=sys.stderr)
        produced_total = None

    # --- bytes consumed (egress) per topic ---
    print("\nQuerying bytes consumed (metric: io.confluent.kafka.server/sent_bytes) ...")
    try:
        consumed = query_metric(
            headers=headers,
            metric_name="io.confluent.kafka.server/sent_bytes",
            resource_field="resource.kafka.id",
            resource_id=cluster_id,
            group_by=["metric.topic"],
            granularity="PT1M",
            minutes=minutes,
            limit=200
        )
        consumed_total = normalize_and_print_timeseries(consumed, "bytes_consumed (sent_bytes)")
    except Exception as e:
        print("Error querying bytes consumed:", e, file=sys.stderr)
        consumed_total = None

    # --- cluster load metric (if available) ---
    print("\nQuerying cluster load (if available). First trying metric name 'cluster_load_percent' ...")
    try:
        cluster_load_resp = query_metric(
            headers=headers,
            metric_name="cluster_load_percent",
            resource_field="resource.kafka.id",
            resource_id=cluster_id,
            group_by=None,
            granularity="PT1M",
            minutes=minutes
        )
        _ = normalize_and_print_timeseries(cluster_load_resp, "cluster_load_percent")
    except Exception as e:
        print("cluster_load_percent not available or query failed:", e)

    # --- CPU metric (example metric name used in docs) ---
    print("\nQuerying CPU percent (metric: io.confluent.kafka.server/cluster_load_percent) ...")
    try:
        cpu_resp = query_metric(
            headers=headers,
            metric_name="io.confluent.kafka.server/cluster_load_percent",
            resource_field="resource.kafka.id",
            resource_id=cluster_id,
            group_by=None,
            granularity="PT1M",
            minutes=minutes
        )
        _ = normalize_and_print_timeseries(cpu_resp, "cpu_load_percent (io.confluent.kafka.server/cluster_load_percent)")
    except Exception as e:
        print("CPU metric query failed:", e)

    print("\nDone.")


if __name__ == "__main__":
    main()