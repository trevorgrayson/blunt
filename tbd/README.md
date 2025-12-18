# tbd

Data utilities for effective Data Engineers

Key Features:
- data impact reports
- hub-and-spoke schema management

# `tbd impact`

presently databricks only
```
tbd impact {catalog} {schema}
```
## Schemas

Utilities can be used to gather, define, and transfer schemas between systems.

- Get established schemas from databases: MySQL, Spark/Databricks
- pidgin schema definitions

A "hub & spoke" model is used to effectively gather and transfer to other systems.

- DBT Sources (virtually all data products)
- ANSI SQL DDLs
- TSV, JSON
