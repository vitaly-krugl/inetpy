import pkg_resources
from setuptools import setup, find_packages



name = "inetpy"



setup(
    name = name,
    version = pkg_resources.resource_stream(__name__, "VERSION").read().strip(),
    description = "Internet Utilities",
    packages = find_packages(),
)
