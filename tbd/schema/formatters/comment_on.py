from ..typemap import convert_mysql2spark
from schemer import dir_for

def control_msg2comment(msg: dict):
    """
    TODO
    - NULLABLE
    - PARTITIONING
    - CLUSTERING
    - COMMENT
    - TBL PROPS
    https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-table-using

    :param msg: DMS control message
    :return: DDL CREATE TABLE statement
    """
    value = msg["value"]
    metadata = value["metadata"]
    database = metadata["schema-name"]
    table_name = metadata['table-name']
    table_def = value["control"]["table-def"]
    columns = table_def["columns"]
    pks = table_def.get("primary-key", [])
    tsv_dir = dir_for(database, "tsv")

    tsv = None
    try:
        tsv = open(f"{tsv_dir}/{database}.{table_name}.tsv", "r")
    except FileNotFoundError:
        print("Build TSV files before running this step.")

    # table
    lines = tsv.readlines()
    table = lines.pop(0)
    table = table.split("\t")

    optional = ""
    if len(pks) > 0:
        optional = " PRIMARY KEY: " + ", ".join(pks)
    out = f"COMMENT ON TABLE {database}.{table_name} IS '{table[-1].strip()}{optional}';\n"

    for col in lines:
        try:
            database, table_name, column_name, type_, desc = col.split("\t")
        except ValueError:
            print(col)
        # col_fields = col.split("\t")
        # col = col_fields[2]
        # desc = col_fields[-1]
        out += f"COMMENT ON COLUMN {database}.{table_name}.{column_name} IS '{desc.strip()}';\n"

    return out