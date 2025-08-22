"""
setup.py configuration script describing how to build and package this project.

This file is primarily used by the setuptools library and typically should not
be executed directly. See README.md for how to deploy, test, and run
"""

from setuptools import setup # , find_packages

import sys

sys.path.append(".")

import datetime

# local_version = datetime.datetime.utcnow().strftime("%Y%m%d.%H%M%S")

setup(
    name="blunt",
    # We use timestamp as Local version identifier (https://peps.python.org/pep-0440/#local-version-identifiers.)
    # to ensure that changes to wheel package are picked up when used on all-purpose clusters
    version="0.0.1", # .__version__ + "+" + local_version,
    url="https://trevorgrayson.com",
    author="trevor@trevorgrayson.com",
    description="Automating the Blunt end of the office.",
    packages=["meet", "dossier"],  # find_packages(where="./src"),
    package_dir={"": "."},
    entry_points={
        "console_scripts": [
            "blunt=widget:main",
            "meet=meet:main",
            "dossier=dossier:main",
        ],
        "packages": [
            # "main=meet" # "main=meet.main:main",
        ],
    },
    install_requires=[
        # Dependencies in case the output wheel file is used as a library dependency.
        # For defining dependencies, when this package is used in Databricks, see:
        # https://docs.databricks.com/dev-tools/bundles/library-dependencies.html
        # "setuptools"
    ],
)
