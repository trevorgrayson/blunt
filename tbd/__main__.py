"""
Schema extraction
"""
import argparse
from argparse import ArgumentParser
from .schema import schema
from .impact import impact

DATA_STORE = "databricks"

"""
impact reports
tbd impact
"""
parser = ArgumentParser("data utilities")
parser.add_argument("verb",
                    help="schema only supported at this time")
# parser.add_argument("verb",
#                     help="tra")
# parser.add_argument("in_file",
#                     help="input schema format"
#                     )
# parser.add_argument("out",
#                     help="output schema format")
parser.add_argument("--database", default=None,
                    help="database name")
parser.add_argument("--vendor", default=DATA_STORE,
                    help="database service")
parser.add_argument("rest", nargs=argparse.REMAINDER)

if __name__ == "__main__":
    args = parser.parse_args()
    match args.verb:
        case "schema":
            schema(args)
        case "impact":
            impact(*args.rest)
        case _:
            raise NotImplementedError(f"Verb {args.verb} not implemented")
