from os import makedirs, environ, path
from glob import glob
from shutil import move

HOME = environ['HOME']
DATA_DIR = path.join(HOME, '.meet/.materials')
TARGET_DIR = path.join(HOME, 'Desktop')

# e.g. Screenshot 2025-08-27 at 10.53.33 AM
screen_shots = glob(path.join(TARGET_DIR, 'Screenshot*.png'))


for filename in screen_shots:
    print(filename)
    try:
        date = filename.split(' ')[1].split('-')
    except Exception:
        continue

    to = path.join(DATA_DIR, *date)

    makedirs(to, exist_ok=True)
    move(path.join(TARGET_DIR, filename), to + '/')
    print(path.join(to, filename))