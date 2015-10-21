
import copy
import functools
import os
import re
import sh
from path import Path

from kea2.util import register_hook
from kea2.log import get_logger

lg = get_logger(__name__, 'warning')

find_inout = re.compile(r'\{([imoxd])(?: ([A-Za-z][\w]*))?\}')


def parse_inout(meta):

    #first - start with the parameter descriptions
    for pname, pdata in meta['_parameters'].items():
        if not 'io' in pdata:
            continue

        category = pdata['io']
        if ':' in category:
            category, name = category.split(':')
        else:
            name = dict(
                i='input',
                o='output',
                x='executable',
                m='misc',
                d='database')[category]

        pval = meta[pname]
        if isinstance(pval, list):
            filenames = copy.copy(pval)
        else:
            filenames = [pval]
        filenames = [str(Path(x).expand()) for x in filenames]

        #put the files in the meta structure
        filenames.extend(meta['_io'][category].get(name, []))
        meta['_io'][category][name] = list(set(filenames))

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
            newfile = Path(src_split[matchloc]).expand()
            filenames.append(str(newfile))
            lastmatch = matchloc

        filenames.extend(meta['_io'][category].get(name, []))
        meta['_io'][category][name] = list(set(filenames))

    for tr in to_remove:
        trloc = src.index(tr)
        if trloc > 0:
            assert src[trloc-1] in [' ', '\n', '\t']
        if tr + ' ' in src:
            lg.debug("removing: %s", tr)
            src = src.replace(tr + ' ', '')

    meta['_src'] = src


def init(meta):
    lg.debug("Initializing inout plugin")
    register_hook('check_execute', parse_inout, order=50)
