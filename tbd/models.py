import json


class Column:
    def __init__(
        self,
        name,
        dtype=None,
        nullable=None,
        default=None,
        primary_key=None,
        unique=None,
        metadata=None,
        **extra
    ):
        if not name or not isinstance(name, str):
            raise ValueError("Column name must be a non-empty string")

        self.name = name
        self.dtype = dtype or extra.get("type")
        self.nullable = nullable
        self.default = default
        self.primary_key = primary_key
        self.unique = unique
        self.metadata = metadata or {}

        if self.primary_key:
            self.nullable = False
            self.unique = True

    def __repr__(self):
        flags = []
        if self.primary_key:
            flags.append("pk")
        if self.unique and not self.primary_key:
            flags.append("unique")
        if not self.nullable:
            flags.append("not null")

        flag_str = f" ({', '.join(flags)})" if flags else ""
        return f"Column({self.name}: {self.dtype}{flag_str})"


class Table:
    def __init__(self, name, columns, **kwargs):
        self.name = name
        self._columns = {}
        self.description = kwargs.get("description")
        self.filename = kwargs.get("filename")

        for col in columns:
            self.add_column(col)

        self._validate_primary_key()

    def add_column(self, column):
        if isinstance(column, dict):
            column = Column(**column)
        if column.name in self._columns:
            raise ValueError(
                f"Duplicate column '{column.name}' in table '{self.name}'"
            )
        self._columns[column.name] = column

    def _validate_primary_key(self):
        pks = [c for c in self._columns.values() if c.primary_key]
        if len(pks) > 1:
            raise ValueError(
                f"Table '{self.name}' has multiple primary keys "
                "(composite keys not yet supported)"
            )

    @property
    def columns(self):
        return list(self._columns.values())

    def column(self, name):
        try:
            return self._columns[name]
        except KeyError:
            raise KeyError(
                f"Column '{name}' not found in table '{self.name}'"
            )

    @property
    def primary_key(self):
        for col in self._columns.values():
            if col.primary_key:
                return col
        return None

    def __repr__(self):
        cols = " ".join([f'{c.name}:{c.dtype}' for c in self.columns])
        return f"{self.name} ({cols})"


class Database:
    def __init__(self, name):
        if not name or not isinstance(name, str):
            raise ValueError("Database name must be a non-empty string")

        self.name = name
        self._tables = {}

    def add_table(self, table):
        if table.name in self._tables:
            raise ValueError(
                f"Table '{table.name}' already exists in database '{self.name}'"
            )
        self._tables[table.name] = table

    def table(self, name):
        try:
            return self._tables[name]
        except KeyError:
            raise KeyError(
                f"Table '{name}' not found in database '{self.name}'"
            )

    @property
    def tables(self):
        return list(self._tables.values())

    def __repr__(self):
        return f"DATABASE({self.name}, tables={[t.name for t in self.tables]})"

#
# results
#

class ImpactReport:
    def __init__(self, graph):
        self.graph = graph

    def save(self, output_path):
        with open(output_path, "w") as f:
            json.dump(self.graph, f, indent=2)

    def write_report(self, output_path):
        with open(output_path + ".tsv", "w") as f:
            f.write(
                "\t".join(["dataset", "owner", "created_by", "updated_by", "email"])
            )
            for dataset, d in self.graph.items():
                metadata = d["metadata"]
                downstream = d["downstream"]
                f.write(
                    "\t".join(map(str,
                                  [dataset, metadata["owner"], metadata["created_by"], metadata["updated_by"],
                                   metadata["email"]]
                                  )) + "\n"
                )
