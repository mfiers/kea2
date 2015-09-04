
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

    cl_tempfile = tempfile.NamedTemporaryFile(delete=False)
    cl_tempfile.write(meta['_src'].encode('UTF-8'))
    cl_tempfile.close()

    mad_save = []
    for cat in iodata:
        for fgroup in iodata[cat]:
            for fname in iodata[cat][fgroup]:
                mad_save.append(fname)
                for_ta[{'i': 'input',
                        'o': 'output',
                        'm': 'misc',
                        'x': 'executable',
                        'd': 'db'}[cat]].append('%s:%s' % (fgroup, fname))

    to_add.append('mad save \\\n    %s' % " \\\n    ".join(mad_save))
    to_add.append("")

    #record transcation
    if for_ta['output']:
        to_add.append("mad ta add \\")
        for cat in for_ta:
            for val in for_ta[cat]:
                to_add.append("   --%s %s \\" % (cat, val))
        to_add.append("   --cl %s" % (cl_tempfile.name))
        to_add.append("rm %s" % (cl_tempfile.name))

    if not 'epilog_single' in  meta['_blocks']:
        meta['_blocks']['epilog_single'] = ""
    meta['_blocks']['epilog_single'] += '\n' + '\n'.join(to_add)

def init(meta):
    lg.debug("Initializing MAD plugin")
    register_hook('to_execute', add_mad_stuff, order=100)
