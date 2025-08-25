from os import path, environ

from .models import Employee
import csv
from argparse import ArgumentParser

DATA_CSV = environ.get('DOSSIER_CSV_FILE', environ['HOME'] + '/data/dossier.csv')


def main():
    parser = ArgumentParser(description='dossier: human lookup')
    parser.add_argument('name', nargs='?',
                        help='name to lookup')
    parser.add_argument('--format', default="display",
                        help='[tab|default] default: multiline')

    args = parser.parse_args()

    if not args.name:
        parser.print_help()
        return

    everyone = {}
    result = []
    #if path.exists(args.csv):
    with open(DATA_CSV, 'r') as f:
        reader = csv.DictReader(f, delimiter='\t')
        name_key = reader.fieldnames[0]  # first column is their name

        for row in reader:
            # row['name'] = row[name_key]
            row['name'] = row.get(name_key)
            emp = Employee(**dict(row))
            everyone[emp.email] = emp

            if emp.match(args.name):
                result.append(emp)

        for ea in everyone.values():
            if ea.manager in everyone.keys():
                ea.manager = everyone[ea.manager]

        for res in result:
            match args.format:
                case "tab":
                    print("\t".join(map(str, (res.name, res.email, res.subteam))))
                case _:
                    print(res)
            print()