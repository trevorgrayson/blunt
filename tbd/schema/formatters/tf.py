TEMPLATE = """
resource "databricks_table" "thing" {
  provider           = databricks.workspace
  name               = "quickstart_table"
  catalog_name       = databricks_catalog.sandbox.id
  schema_name        = databricks_schema.things.name
  table_type         = "MANAGED"
  data_source_format = "DELTA"
  column {
    name      = "id"
    position  = 0
    type_name = "INT"
    type_text = "int"
    type_json = "{\"name\":\"id\",\"type\":\"integer\",\"nullable\":true,\"metadata\":{}}"
  }
  column {
    name      = "name"
    position  = 1
    type_name = "STRING"
    type_text = "varchar(64)"
    type_json = "{\"name\":\"name\",\"type\":\"varchar(64)\",\"nullable\":true,\"metadata\":{}}"
  }
  comment = "this table is managed by cdcetl terraform"
}
"""