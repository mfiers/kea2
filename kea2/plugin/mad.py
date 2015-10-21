
from collections import defaultdict
import os
from pprint import pprint
import re
import tempfile
import shlex
import time

from path import Path

from kea2.util import register_hook
from kea2.log import get_logger

lg = get_logger(__name__, 'info')

def add_mad_stuff(meta):

    iodata = meta['_io']
    if len(iodata) == 0:
        return

    to_add = []
    for_ta = defaultdict(list)

    for cat in iodata:
        for fgroup in iodata[cat]:
            for fname in iodata[cat][fgroup]:
                for_ta[{'i': 'input',
                        'o': 'output',
                        'm': 'misc',
                        'x': 'executable',
                        'd': 'db'}[cat]].append('%s:%s' % (fgroup, fname))


    #record transcation
    if for_ta['output']:
        to_add.append("mad ta add \\")
        for cat in for_ta:
            for val in for_ta[cat]:
                to_add.append("   --%s %s \\" % (cat, val))
        to_add.append("   --script {{_cmd_file}}")

    epsingle = meta['_blocks'].get('epilog_single', "")
    epsingle = '\n'.join(to_add) + "\n##\n" + epsingle
    meta['_blocks']['epilog_single'] = epsingle

def init(meta):
    lg.debug("Initializing MAD plugin")
    register_hook('to_execute', add_mad_stuff, order=-1)
