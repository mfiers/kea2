
import os
import re
from path import Path

from kea2.util import register_hook
from kea2.log import get_logger

lg = get_logger(__name__, 'warning')

find_inout = re.compile(r'{([imoxd])(?: ([A-Za-z][\w]*))?}')


def parse_inout(meta):

    src = meta['_src']

    rex = r'("\S*?"|\'.*?\'|\{\{.*?\}\}|\{.*?\}|\s)'
    src_split = [x.strip() for x in re.split(rex, src) if x.strip()]

    to_remove = set()

    for hit in find_inout.finditer(src):

        match = hit.group(0)
        to_remove.add(match)
        category, name = hit.groups()

        if name is None:
            name = dict(
                i='input',
                o='output',
                x='executable',
                m='misc',
                d='database')[category]

        lastmatch = 0
        filenames = []

        while True:
            try:
                matchloc = src_split.index(match, lastmatch) + 1
            except ValueError:
                break
            filenames.append(str(Path(src_split[matchloc]).expand()))
            lastmatch = matchloc

        for fn in filenames:
            lg.debug("found io group: %s/%s : %s", category, name, fn)

        filenames.extend(meta['_io'][category].get(name, []))
        meta['_io'][category][name] = list(set(filenames))

    for tr in to_remove:
        if ' ' + tr + ' ' in src:
            lg.debug("removing: %s", tr)
            src = src.replace(tr + ' ', '')

    meta['_src'] = src


def init(meta):
    lg.debug("Initializing inout plugin")
    register_hook('check_execute', parse_inout, order=50)
