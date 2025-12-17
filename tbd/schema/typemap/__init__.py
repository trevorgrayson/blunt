from .mappings import MYSQL_TO_DATABRICKS_TYPE_MAP


def convert_mysql2spark(mysql_type: str) -> str:
    """
    Convert a MySQL column type to a Databricks SQL column type.

    Optional TODO
    - precision/scale
    - enum

    Args:
        mysql_type (str): The MySQL type string, e.g., "varchar(255)", "int(11)", etc.

    Returns:
        str: The equivalent Databricks SQL type.
    """
    base_type = mysql_type.upper().split('(')[0].strip()
    return MYSQL_TO_DATABRICKS_TYPE_MAP.get(base_type, 'STRING')  # default fallback to STRING
