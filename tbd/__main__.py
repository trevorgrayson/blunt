"""
Schema extraction
"""
import argparse, sys
from argparse import ArgumentParser
from .schema import schema_read, write_table, table_print, from_source_yaml
from .impact import impact
from enum import Enum
from os.path import join
from .editor import editor

DATA_STORE = "databricks"

"""
impact reports
tbd impact
"""
EPILOG = """verbs:
    impact: analyze downstream dependencies on schemas
"""

HUB = "hub"
PRINT = "print"


parser = ArgumentParser("data utilities",
                        formatter_class=argparse.RawTextHelpFormatter,
                        description="data utilities for business value.",
                        epilog=EPILOG
                        )
parser.add_argument("verb",
                    help="schema only supported at this time")
# parser.add_argument("verb",
#                     help="tra")
parser.add_argument("--origin", dest="origin", default=HUB,
                    help="origin dataset, pipeline, or files to extract from. Defaults to the HUB.")
parser.add_argument("--dest", default=HUB,
                    help="destination dataset, docs to act upon. Defaults to the HUB")

parser.add_argument("--hub", default=f"./{HUB}",
                    help="hub working directory definition.")

parser.add_argument("--database", default=None,
                    help="database name")
parser.add_argument("--vendor", default=DATA_STORE,
                    help="database service")
parser.add_argument("rest", nargs=argparse.REMAINDER)

if len(sys.argv) == 1:
    parser.print_help()
    sys.exit(0)

def main():
    """
    controller for tbd verbs.

    :return:
    """
    args = parser.parse_args()

    origin = args.origin
    if origin == HUB:
        origin = args.hub
    print(f"origin: {origin}")

    dest = args.dest
    if dest == "hub":
        dest = args.hub

    match args.verb:
        case "schema": # read in schema from# file
            # TODO
            schema = schema_read(in_file=origin)
            for table in schema:
                table_print(table)
                write_table(table,
                            database_name=args.database,
                            out_folder=dest)
            print(f"{dest} is current")

        case "show":
            target_table, *rest = args.rest
            schema = schema_read(in_file=origin,
                                 schema_reader=from_source_yaml)
            for table in schema:
                if not target_table:
                    print(table.name)
                elif table.name == target_table:
                    print(table)
        case "edit":
            target_table, *rest = args.rest
            schema = schema_read(in_file=origin,
                                 schema_reader=from_source_yaml)
            for table in schema:
                if table.name == target_table:
                    editor(table.filename)

        case "impact":
            # TODO, prob OK
            dataset = args.rest
            impact(*dataset,
                   output=(".".join(dataset) + ".impact"))

        case _:
            raise NotImplementedError(f"Verb {args.verb} not implemented")


if __name__ == "__main__":
    main()