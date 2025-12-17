from yaml import dump as yaml_dump
from .typemap import convert_mysql2spark
from tbd.models import *
from collections import OrderedDict

def schema_csv_to_hub(fp):
    """
    Convert a schema in CSV format to a dictionary representation.
    Assumes first line is header with column names.

    table_name,column_name,data_type
    """
    import csv

    reader = csv.DictReader(fp)
    table = None
    for row in reader:
        table_name, column_name, data_type = row.values()
        if table is None or table.name != table_name:
            if table is not None:
                yield table
            table = Table(name=table_name, columns=[])
        table.add_column(Column(name=column_name, dtype=data_type))

    yield table


def to_source_yaml(table, database_name=None):
    """
    Convert to DBT Source YAML format.
    :return:
    """
    sources_mock = {
        "sources": {
            "columns": [
                dict(OrderedDict({
                    "name": col.name,
                    "type": col.dtype,
                    "description": col.dtype
                })) for col in table.columns
            ]
        }
    }

    cols = [f"""
    - name: {col.name}
      type: {convert_mysql2spark(col.dtype)}
      description:
    """ for col in table.columns]
    return f"""
version: 2

sources:
- name: {database_name or ''}
  database: {database_name or ''}
  tables:
  description: "Auto-Generated Documentation from TBD"
  - name: {table.name}
    columns:
    { "".join(cols)}
"""

def schema(args):
    # convert schema formats

    ## FROM
    in_file = open(args.in_file, "r")
    hub = schema_csv_to_hub(in_file)

    # ditch fivetran tables
    # _fivetran... columns

    for table in hub:
        out_filename = f"{args.out}/{table.name}.source.yaml"
        print(out_filename)
        with open(out_filename, "w") as out_fp:
            out_fp.write(to_source_yaml(table, args.database))

    in_file.close()