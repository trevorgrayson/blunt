import subprocess
from os import environ

EDITOR = environ.get("EDITOR")

def editor(filename):
    # TODO if editor == 'ncurses',
    # present ncurses form editor
    # user should be able to fill out standard DBT Source YAML fields,
    # ownership, and contact information including a team, email,
    # and a slack channel
    if EDITOR is None:
        raise NotImplementedError("EDITOR environment variable not set")
    subprocess.run([EDITOR, filename])