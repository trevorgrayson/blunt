from os import environ
from json import loads
from http.client import HTTPSConnection
from datetime import datetime, timezone
from urllib.parse import quote

SETUP_INSTRUCTION = """
Head to Datadog API to get your credentials and configure your environment.
https://app.datadoghq.com/personal-settings/application-keys

```
export DATADOG_API_KEY=<your-api-key>
```
"""
class DatadogException(Exception):
    pass


class DataDog:
    def __init__(self, api_key, app_key, hostname="api.datadoghq.com"):
        self.api_key = api_key
        self.app_key = app_key
        self.conn = HTTPSConnection(hostname)

    def headers(self):
        return {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            "DD-API-KEY": self.api_key,
            "DD-APPLICATION-KEY": self.app_key
        }

    def request(self, method, path, params=None):
        self.conn.request(method, path,
                          headers=self.headers())
        response = self.conn.getresponse()
        if response.status == 200:
            resp = response.read().decode('utf-8')
            return loads(resp)
        else:
            resp = response.read().decode('utf-8')
            raise DatadogException(response.status)

    def query(self, query, from_=None, to_=None):
        """
        Query timeseries points. This endpoint requires the timeseries_query permission.
        OAuth apps require the timeseries_query authorization scope to access this endpoint

        :param query:
        :param from_:
        :param to_:
        :return:
        """
        if to_ is None:
            to_ = now = int(datetime.now(tz=timezone.utc).timestamp())
        if from_ is None:
            from_ = now - 86400 # 24 hours

        qs = f"/api/v1/query?from=${from_}&to=${to_}&query=${quote(query)}"
        return self.request("GET", qs)

    def query_scalar(self, *metrics):
        """
        Get metadata about a specific metric. This endpoint requires the metrics_read permission.
        OAuth apps require the metrics_read authorization scope to access this endpoint.

        :return:
        """
        body = {
            "data": {
                "attributes": {
                    "formulas": [
                        {
                            "formula": "a",
                            "limit": {
                                "count": 10,
                                "order": "desc"
                            }
                        }
                    ],
                    "from": 1636625471000,
                    "queries": [
                        {
                            "aggregator": "avg",
                            "data_source": "metrics",
                            "query": "avg:system.cpu.user{*}",
                            "name": "a"
                        }
                    ],
                    "to": 1636629071000
                },
                "type": "scalar_request"
            }
        }
        return self.request("POST", f"/api/v2/query/scalar")