def sql_parse(sql: str) -> dict:
    pass


def sql_fingerprint(sql):
    """
    /{database}/{table}/{filter-columns}/{select-columns}
    Use details - user, query time, cost, frequency
    :param sql:
    :return:
    """
    return (
        sql.database,
        sql.table,
        sql.filter,
        sql.columns,
    )