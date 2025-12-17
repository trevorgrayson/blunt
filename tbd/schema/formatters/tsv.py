from ..typemap import convert_mysql2spark


def control_msg2tsv(msg: dict, write_dir=None):
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

    fp = open(f"{write_dir}/{database}.{table_name}.tsv", "w") if write_dir else None
    # table
    out = "\t".join((database, table_name, '', '', " ".join(pks), "Auto-Generated Documentation from cdcetl schemer"))
    out += "\n"
    # columns
    for col_name, ty in columns.items():
        type_ = convert_mysql2spark(ty["type"])

        # database, table_name[, col_name, type_], pks, description
        out += "\t".join((
            database,
            table_name,
            col_name,
            type_,
            f"PRIMARY KEY: {' '.join(pks)} (MySQL:{ty['type']})"\
                if col_name in pks else f"(MySQL: {ty['type']})"
        ))
        out += "\n"

    if fp:
        fp.write(out + "\n")
    if fp is not None:
        fp.close()

    return out