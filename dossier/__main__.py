from argparse import ArgumentParser
from os import path, environ
from .models import Employee
import csv

DATA_CSV = environ.get('DOSSIER_CSV_FILE', environ['HOME'] + '/data/dossier.csv')

parser = ArgumentParser(description='dossier: human lookup')

parser.add_argument('name', nargs='?',
                    help='name to lookup')
# parser.add_argument('--csv', default=DATA_CSV,
#                     help='path to csv file')

args = parser.parse_args()

everyone = {}
result = []
#if path.exists(args.csv):
with open(DATA_CSV, 'r') as f:
    csv = csv.DictReader(f, delimiter='\t')
    name_key = csv.fieldnames[0]  # first column is their name

    for row in csv:
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
        print(res)
        print()