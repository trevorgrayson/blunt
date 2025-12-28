from yaml import dump as yaml_dump
import yaml
from .typemap import convert_mysql2spark
from tbd.models import *
from collections import OrderedDict
from glob import glob
from os.path import join, isdir, isfile
from os import makedirs

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
            table = Table(name=table_name, columns=[], filename=fp.name)
        table.add_column(Column(name=column_name, dtype=data_type))

    yield table


def from_source_yaml(fp, database_name=None):
    data = yaml.safe_load(fp)

    for source in data.get("sources", []):
        # TODO schema!
        # print(source.get("name", "New Source"))

        for d in source.get("tables", []):
            table = Table(**d, filename=fp.name)
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
  
  - name: {table.name}
    description: "Auto-Generated Documentation from TBD"
    columns:
    { "".join(cols)}
"""

def write_table(table, out_folder=None, database_name=None, formatter=None):
    """
    :param table_name:
    :param out_folder:
    :param database_name:
    :param formatter:
    :return:
    """
    if formatter is None:
        formatter = to_source_yaml
    out = []
    if out_folder:
        out.append(out_folder)
    if database_name:
        out.append(database_name)
    makedirs(join(*out), exist_ok=True)
    out_filename = join(*out, f"{table.name}.source.yaml")
    with open(out_filename, "w") as out_fp:
        out_fp.write(formatter(table, database_name))


def schema_read(schema_reader=None, **kwargs):
    """
    SHOULD return iterable schema object.
    :param args:
    :return:
    """
    if schema_reader is None:
        schema_reader = schema_csv_to_hub
    in_file = kwargs.get('in_file', '**/*')
    if isdir(in_file):
        in_file = join(in_file, '*')

    for filename in glob(in_file):
        if not isfile(filename):
            continue

        in_file = open(filename, "r")
        hub = schema_reader(in_file)

        for table in hub:
            yield table

def table_print(table):
    print(table)