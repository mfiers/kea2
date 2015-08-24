
from itertools import chain
import os
from pprint import pprint
import re
import time

from path import Path

from kea2.util import register_hook
from kea2.log import get_logger

lg = get_logger(__name__, 'info')

find_inout = re.compile(r'{([ioxd])(?: ([A-Za-z][\w]*))?}')

def file_time_report(ot, idxt):
    oldest_output = min(ot.values())
    newest_input = max(idxt.values())

    fmt = lambda x: time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(x))

    print("# newest input  :", fmt(newest_input))
    print("# oldest output :", fmt(oldest_output))

    for (c, g, f), t in ot.items():
        flag = '>' if t < newest_input else ' '
        print('%s %s %-10s %s %s' % (flag, c, g, fmt(t), f))
    for (c, g, f), t in idxt.items():
        flag = '<' if t > oldest_output else ' '
        print('%s %s %-10s %s %s' % (flag, c, g, fmt(t), f))


def check_newer(meta):

    io = meta['_io']

    if not 'o' in io:
        lg.debug("no output files defined - continue")
        return
    if not 'i' in io or not 'd' in io:
        lg.debug("no input or database files defined - continue")
        return

    def get_all_files(_io, _cat):
        for outgroup in io[_cat]:
            for outfile in io[_cat][outgroup]:
                yield _cat, outgroup, Path(outfile)

    output_timestamps = {}

    for _, outgrp,  outfile in get_all_files(io, 'o'):
        if not outfile.exists():
            #file does not exist - do not skip
            lg.warning("cannot find: %s/%s (run)", outgrp, outfile)
            return

        output_timestamps[('o', outgrp, outfile)] = outfile.mtime

    idx_timestamps = {}
    for _cat, grp, idx_file in chain( get_all_files(io, 'i'),
                                      get_all_files(io, 'd'),
                                      get_all_files(io, 'x')  ):
        if not idx_file.exists():
            #file does not exist - do not skip
            lg.warning("cannot find %s file: %s/%s (run anyway??)", _cat, grp, infile)

        idx_timestamps[(_cat, grp, idx_file)] = idx_file.mtime

    oldest_output = min(output_timestamps.values())
    newest_input = max(idx_timestamps.values())

    if newest_input > oldest_output:
        lg.warning("newest input file is older than oldest output fil (run)")
        file_time_report(output_timestamps, idx_timestamps)
    else:
        lg.debug("oldest output file is newer than youngest input file (skip)")
        meta['_skip'] = True


def init(meta):
    lg.debug("Initializing skip_newer plugin")
    register_hook('check_execute', check_newer, order=100)
