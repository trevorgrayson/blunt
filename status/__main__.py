from os import environ, path
from argparse import ArgumentParser
from configparser import ConfigParser
import importlib
parser = ArgumentParser("status",
                        description="comprehensive systems status update")
parser.add_argument("-s", "--service", default="all",
                    help="service to display")

args = parser.parse_args()

CONFIG = environ.get("STAT_CONFIG", path.join(environ["HOME"], ".status.ini"))

config = ConfigParser()

if path.exists(CONFIG):
    config.read_file(open(CONFIG, 'r'))

    for section in config.sections():
        print(section, end='...\t\t')
        selector = None


        try:
            client = importlib.import_module("clients." + section)
            data = client.status()

            if config.has_option(section, "selector"):
                selector = config.get(section, "selector")
                print(data[selector])
            else:
                print(data)

        except ImportError:
            print("module not found in clients.")

else:
    print("no config file")
    while(True):
        section = input("New Service Monitor Name [Ctrl-C to quit]:")
        config.add_section(section)
        config.set(section, "url", input("url:"))
        config.write(open(CONFIG, 'w'))

