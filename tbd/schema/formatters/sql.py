from ..typemap import convert_mysql2spark


def control_msg2ddl(msg: dict):
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
    table_def = value["control"]["table-def"]
    columns = table_def["columns"]
    pks = table_def.get("primary-key", [])

    table_spec = []
    for col_name, ty in columns.items():
        type_ = convert_mysql2spark(ty["type"])
        table_spec.append(
            f"  {col_name}  {type_}"
        )
    table_spec_s = "\n".join(table_spec)
    cluster_by = f"CLUSTER BY {','.join(pks)}"

    return f"""CREATE TABLE IF NOT EXISTS {metadata['table-name']} (
{table_spec_s}

{cluster_by if len(pks) > 0 else ''}
);
"""