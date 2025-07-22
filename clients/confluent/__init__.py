
from os import environ
from http.client import HTTPSConnection
from json import dumps, loads
from base64 import b64encode
from collections import namedtuple
# from metric_configs import Metrics

QUERY_PATH = "/v2/metrics/cloud/query"
KEY = environ.get("CONFLUENT_KEY")
SECRET = environ.get("CONFLUENT_SECRET")
TOKEN = environ.get("CONFLUENT_TOKEN")
FILTER = environ.get("CONFLUENT_FILTER")
from enum import Enum


class Metrics(Enum):
    ConsumerLag = "io.confluent.kafka.server/consumer_lag_offsets"
    TopTopics = "io.confluent.kafka.server/received_bytes"


# TODO
# cluster_load_percent_max
# cluster_load_percent_avg
# io.confluent.kafka.server/producer_latency_avg_milliseconds
# io.confluent.kafka.server/cluster_load_percent
ConsumerLag = namedtuple("ConsumerLag", ["value", "group", "topic"])
BytesPer = namedtuple("BytesPer", ["timestamp", "value"])
# ClusterMetrics
class Confluent:
    def __init__(self,  key=KEY, secret=SECRET, token=TOKEN, host="api.telemetry.confluent.cloud",
                 filter=FILTER):
        self.host = host
        self.conn = HTTPSConnection(host)
        self.filter = filter
        self.token = b64encode(bytes(f"{key}:{secret}", 'utf-8')).decode('utf-8')  # padding

    @property
    def headers(self):
        return {
            "Content-Type": "application/json",
            "Accepts": "application/json",
            "Authorization": f"Basic {self.token}"
        }

    def query(self, metric:Metrics, group_by):
        body = self.cluster_query(metric, group_by)
        return self.request(body)

    def request(self, body, method="POST"):
        # raise Exception(self.headers)
        self.conn.request(method, QUERY_PATH,
                          body=dumps(body),
                          headers=self.headers)
        resp = self.conn.getresponse()

        if resp.status == 200:
            data = resp.read()
            return loads(data)
        raise Exception(str(resp.status) + str(resp.reason) + str(resp.read()))

    def consumer_lag(self, limit=25):
        metric = "io.confluent.kafka.server/consumer_lag_offsets"
        group_by = ["metric.consumer_group_id", "metric.topic"]


        data = self.request(self.cluster_query(
            metric=Metrics.ConsumerLag,
            filter=self.filter,
            group_by=["metric.consumer_group_id", "metric.topic"]
        ))

        return [ConsumerLag(row["value"], row["metric.topic"], row["metric.consumer_group_id"])
                for row in data['data']]

    def top_topics(self, granularity="PT1M", limit=25):
        query = {
          "aggregations": [
            {"metric": "io.confluent.kafka.server/received_bytes"}
          ],
          "filter": {
            "field": "resource.kafka.id",
            "op": "EQ",
            "value": self.filter
          },
          "granularity": granularity,
          "group_by": [
            "metric.topic"
          ],
          "intervals": [
            f"PT1H/now"
          ],
          "limit": limit
        }
        data = self.request(query)
        return [row
                for row in data["data"]]

    def cluster_load(self, granularity="PT1M", limit=25): # TODO
        # io.confluent.kafka.server/cluster_load_percent
        query = {
            "aggregations": [{"metric": "confluent.kafka.server/cluster_load_percent"}],
            "filter": {
                "field": "resource.kafka.id",
                "op": "EQ",
                "value": self.filter
            },
            "granularity": granularity,
            "intervals": [
                f"PT1H/now"
            ],
            "limit": limit
        }
        data = self.request(query)
        return [row
                for row in data["data"]]

    def received_bytes(self, granularity="PT1M", limit=100):
        query = {
          "aggregations": [{"metric": "io.confluent.kafka.server/received_bytes"}],
          "filter": {
            "field": "resource.kafka.id",
            "op": "EQ",
            "value": self.filter
          },
          "intervals": [
            "PT1H/now"
          ],
          "granularity": "PT1M",
          "limit": limit
        }

        data = self.request(query)
        return [BytesPer(**row)
                for row in data["data"]]

    # io.confluent.kafka.server/producer_latency_avg_milliseconds
    # io.confluent.kafka.server/sent_bytes
    # io.confluent.kafka.server/received_records
    # io.confluent.kafka.server/sent_records
    # io.confluent.kafka.server/received_bytes
    # io.confluent.kafka.server/response_bytes

    def cluster_query(self, metric: Metrics, group_by, filter=None, granularity="PT1H", limit=25):
        if group_by is None:
            group_by = []
        if isinstance(group_by, str):
            group_by = [group_by]
        if filter is None:
            filter = self.filter

        query = {
          "aggregations": [{"metric": metric.value}],
          "filter": {
            "field": "resource.kafka.id",
            "op": "EQ",
            "value": filter
          }
        }
        query["group_by"] = group_by

        if granularity is not None:
            query["granularity"] = granularity
            query["intervals"] = [f"{granularity}/now"]
        if limit is not None:
            query["limit"] = limit

        return query