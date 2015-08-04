
from hashlib import sha1
import os
from pprint import pprint
import subprocess as sp
import time


from jinja2 import Environment, FileSystemLoader, Template
from path import Path

import kea2.log
from kea2.util import register_hook
from kea2 import util

lg = kea2.log.get_logger(__name__)


def printer(meta):
    lg.debug("register for execution")
    print(meta['_src'])


def init(meta):
    lg.debug("Initializing print executor")
    register_hook('to_execute', printer, 100)
