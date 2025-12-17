import os
from argparse import ArgumentParser

from . import control_msg2tsv, control_msg2comment
from .sql import control_msg2ddl
from json import loads, decoder
from schemer import dir_for

ROOT_DIR = os.environ["PWD"]

parser = ArgumentParser(description='convert schemas between formats')
parser.add_argument('files', nargs='+')
parser.add_argument("--format", default='ddl', choices=['ddl', 'tsv', 'comment'],
                    help="output format")
parser.add_argument("-w", "--write", action='store_true', default=False,
                    help="write output to files")
args = parser.parse_args()

for file in args.files:
    with open(os.path.join(ROOT_DIR, file)) as f:
        line = None
        try:
            line = f.readline()
            msg = {"value": loads(line)}
            database = msg["value"]["metadata"]["schema-name"]
            match args.format:
                case "ddl":
                    print(control_msg2ddl(msg))
                case "tsv":
                    write_dir = dir_for(database, "tsv") if args.write else None
                    print(control_msg2tsv(msg, write_dir))
                case "comment":
                    print(control_msg2comment(msg))
        except decoder.JSONDecodeError:
            print(f"Error in {file}")
            print(line)
