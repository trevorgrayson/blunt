from os import environ, system, path
from argparse import ArgumentParser
from datetime import datetime

HOME = environ.get("HOME", ".")
MEET_DIR = environ.get("MEET_DIR", f"{HOME}/.meet")


parser = ArgumentParser("meet")
parser.add_argument("name",
                     help="name of meeting or person")
parser.add_argument("agenda", nargs="*", default=[],
                    help="add agenda or note to a meeting")

def main():
    args = parser.parse_args()

    EDITOR = environ.get("EDITOR", "vi")
    path_name = path.join(MEET_DIR, args.name)

    if len(args.agenda) > 0:
        if args.agenda[0] in ['e', 'edit']:
            if EDITOR in ["vi", "vim"]:
                EDITOR = "vi"
                system(f"{EDITOR} -o {MEET_DIR}/.dossier/{args.name} {path_name}")
            else:
                system(f"{EDITOR} {path_name}")
            return

        date_s = datetime.now().strftime("%Y-%m-%d")
        with open(path_name, "a") as f:
            f.write(f"{date_s} ")
            f.write(" ".join(args.agenda))
            f.write("\n")
    
    queue = []
    with open(path_name, "r") as f:
        lines = f.read().split("\n")
        for line in lines:
            queue.append(line)

            if len(queue) > 10:
                queue.pop(0)

    for line in queue:
        print(line)
