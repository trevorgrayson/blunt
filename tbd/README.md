# tbd

Data utilities for effective Data Engineers

Key Features:
- data impact reports
- hub-and-spoke schema management
  - define schemas
  - document schemas
  - make new schemas available for query

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

## the "hub"

the `datahub` folder acts as a working directory, or potentially the definition of, your datasets.

The hub is presumed to be the target if the `origin` or `destiniation` is left empty.

You may define:

* `source` data (data which enters the system),
* `sink`s, or data `exposure`s (uses of data),
* pipelines/transforms, or
* lineage and relationships between data.
