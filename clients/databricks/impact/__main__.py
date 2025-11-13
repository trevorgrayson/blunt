import argparse
import os

from . import *


def main():
    parser = argparse.ArgumentParser(
        description="Discover all downstream dependencies in a Databricks Unity Catalog schema."
    )
    parser.add_argument("--host", required=False, default=os.getenv("DATABRICKS_HOST"),
                        help="Databricks workspace host URL (e.g. https://abc.cloud.databricks.com)")
    parser.add_argument("--token", required=False, default=os.getenv("DATABRICKS_TOKEN"),
                        help="Databricks personal access token (dapi-...)")
    parser.add_argument("--catalog", required=True, help="Catalog name")
    parser.add_argument("--schema", required=True, help="Schema name")
    parser.add_argument("--output", default="downstream_dependencies.json", help="Output file for JSON results")
    parser.add_argument("--delay", type=float, default=0.2, help="Delay between API calls (seconds)")
    args = parser.parse_args()

    print(f"\n🔍 Scanning downstream dependencies for {args.catalog}.{args.schema} ...\n")

    tables = list_tables_in_schema(args.host, args.token, args.catalog, args.schema)
    if not tables:
        print("No tables found in this schema.")
        return

    graph = {}
    visited = set()

    for tbl in tables:
        traverse_downstream(args.host, args.token, tbl, visited, graph, delay=args.delay)

    with open(args.output, "w") as f:
        json.dump(graph, f, indent=2)

    print(f"\n✅ Completed. Found {len(graph)} objects.")
    print(f"📄 Results saved to {args.output}\n")

if __name__ == "__main__":
    main()
