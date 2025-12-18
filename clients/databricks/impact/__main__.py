import argparse
import os

from . import impact



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

    impact(args.catalog, args.schema,
           host=args.host, token=args.token,
           output=args.output, delay=args.delay)

if __name__ == "__main__":
    main()
