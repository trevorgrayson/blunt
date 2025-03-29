from os import environ, system, path
from argparse import ArgumentParser
from datetime import datetime

parser = ArgumentParser("meet")
parser.add_argument("name",
                     help="name of meeting or person")
parser.add_argument("agenda", nargs="*", default=[],
                    help="add agenda or note to a meeting")
args = parser.parse_args()

HOME = environ.get("HOME", ".")
MEET_DIR = environ.get("MEET_DIR", f"{HOME}/.meet")
EDITOR = environ.get("EDITOR", "vi")
path_name = path.join(MEET_DIR, args.name)

if len(args.agenda) > 0:
    date_s = datetime.now().strftime("%Y-%m-%d")
    with open(path_name, "a") as f:
        f.write(f"{date_s} ")
        f.write(" ".join(args.agenda))
        f.write("\n")
else:
    print(EDITOR)
    if EDITOR in ["vi", "vim"]:
        EDITOR = "vi"
        system(f"{EDITOR} -o {MEET_DIR}/.dossier/{args.name} {path_name}")
    else:
        system(f"{EDITOR} {path_name}")
