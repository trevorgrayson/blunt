from os import environ
from . import DataDog

DATADOG_APP_KEY = environ['DATADOG_APP_KEY']
DATADOG_API_KEY = environ['DATADOG_KEY']

client = DataDog(DATADOG_API_KEY, DATADOG_APP_KEY)


metric = "sum(last_1d):avg:aws.dms.cdcchanges_memory_target{replicationinstanceidentifier:fivetran,!replicationtaskidentifier:wlqmyucw2uzsikgvostczmt7f54dfxvupc2odgi ,!replicationtaskidentifier:sneelq7xybprvoxp6acy2kotegrh7m6qkkivvsi ,!replicationtaskidentifier:bubogq4rzoks74ah7heyp7yek7lqjguu6wrok7a , !replicationtaskidentifier:fjoa7dvhpjrlbi645dpnbdn7ft4kbrlpmf3itja} by {replicationtaskidentifier} == 0"
print(client.query(metric))