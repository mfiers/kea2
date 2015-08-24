
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

    tmpl_path = Path('~/kea2/executor/simple/').expanduser()

    jenv = Environment(loader=FileSystemLoader(tmpl_path))
    util.register_jinja2_filters(jenv)

    src = meta['_src']
    meta['command'] = src

    cmd = jenv.get_template('command.template').render(meta)
    print(cmd)


def init(meta):
    lg.debug("Initializing print executor")
    register_hook('to_execute', printer, 100)
