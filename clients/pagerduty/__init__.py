"""
PagerDuty REST API Client

API Documentation: https://developer.pagerduty.com/api-reference/9d0b4b12e36f9-list-incidents
Author: Trevor Grayson
"""
from http.client import HTTPSConnection
from json import loads
from .models import *

HOSTNAME = 'api.pagerduty.com'


class PagerDuty:
    def __init__(self, api_key):
        self.api_key = api_key
        self.conn = HTTPSConnection(HOSTNAME)

    def headers(self):
        return {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f'Token token={self.api_key}'
        }

    def request(self, method, path, params=None):
        query = ''
        if params:
            for k, v in params.items():
                if isinstance(v, list):
                    for val in v:
                        query += f'&{k}[]={val}'
                else:
                    query += f'&{k}={v}'
            query = "?" + query[1:]

        self.conn.request(method, path + query,
                          headers=self.headers())
        response = self.conn.getresponse()
        if response.status == 200:
            resp = response.read().decode('utf-8')
            return loads(resp)
        else:
            resp = response.read().decode('utf-8')
            raise PagerDutyException(f"{response.status}")

    def incidents(self, **params):
        """
        limit
        integer
        The number of results per page. Maximum of 100.

        offset
        integer
        Offset to start pagination search results.

        total
        boolean
        By default the total field in pagination responses is set to null to provide the fastest possible response times. Set total to true for this field to be populated.Show all...

        Default:
        false
        date_range
        string
        When set to all, the since and until parameters and defaults are ignored.

        Allowed value:
        all
        incident_key
        string
        Incident de-duplication key. Incidents with child alerts do not have an incident key; querying by incident key will return incidents whose alerts have alert_key matching the given incident key.

        include[]
        string
        Array of additional details to include.

        Allowed values:
        acknowledgers
        agents
        assignees
        conference_bridge
        escalation_policies
        first_trigger_log_entries
        priorities
        services
        teams
        users
        service_ids[]
        array[string]
        Returns only the incidents associated with the passed service(s). This expects one or more service IDs.

        since (string)
        The start of the date range over which you want to search. Maximum range is 6 months and default is 1 month.

        sort_by
        array[string]
        Used to specify both the field you wish to sort the results on (incident_number/created_at/resolved_at/urgency), as well as the direction (asc/desc) of the results. The sort_by field and direction should be separated by a colon. A maximum of two fields can be included, separated by a comma. Sort direction defaults to ascending. The account must have the urgencies ability to sort by the urgency.

        <= 2 items
        statuses[]
        string
        Return only incidents with the given statuses. To query multiple statuses, pass statuses[] more than once, for example: https://api.pagerduty.com/incidents?statuses[]=triggered&statuses[]=acknowledged. (More status codes may be introduced in the future.)

        Allowed values:
        triggered
        acknowledged
        resolved
        team_ids[]
        array[string]
        An array of team IDs. Only results related to these teams will be returned. Account must have the teams ability to use this parameter.

        time_zone
        string
        <tzinfo>
        Time zone in which results will be rendered. This will default to the account time zone.

        until
        string
        The end of the date range over which you want to search. Maximum range is 6 months and default is 1 month.

        urgencies[]
        string
        Array of the urgencies of the incidents to be returned. Defaults to all urgencies. Account must have the urgencies ability to do this.

        Allowed values:
        high
        low
        user_ids[]
        array[string]
        Returns only the incidents currently assigned to the passed user(s). This expects one or more user IDs. Note: When using the assigned_to_user filter, you will only receive incidents with statuses of triggered or acknowledged. This is because resolved incidents are not assigned to any user.
        :param kwargs:
        :return:
        """
        result = self.request("GET", "/incidents/", params=params)
        return list(map(Incident.new, result["incidents"]))

    def outliers(self, id, params=None):
        result = self.request("GET", "/incidents/{}/outliers".format(id), params=params)
        return list(map(lambda a: Incident(**a), result))

    def related_incidents(self, id, params=None):
        result = self.request("GET", "/incidents/{}/related_incidents".format(id), params=params)
        return list(map(lambda a: Incident(**a), result))