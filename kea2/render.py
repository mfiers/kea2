
from logging import INFO
import re
import shlex

from kea2.log import get_logger

lg = get_logger('k2.render')
lg.setLevel(INFO)

re_find_param_r = (
    r'#p\s+'
    r'(?P<name>[A-Za-z][A-Za-z0-9_]*)'
    r'([ \t]+(?P<keywords>[^\n]+))?'
    r'\n')

re_find_param_embed_r = (
    r'{p\s+'
    r'(?P<name>[A-Za-z][A-Za-z0-9_]*)'
    r'([ \t]+(?P<keywords>[^\n]+))?'
    r'\n')

re_find_param = re.compile(re_find_param_r)

ALLOWED_PARAMETER_FLAGS = """
    opt
    int     float
    hide
""".split()

def find_params(meta):

    src = meta['_src']
    lg.debug("Start render level 01")
    meta['_parameter_order'] = []

    for hit in re_find_param.finditer(src):
        pardata = hit.groupdict()
        lg.debug(str(pardata))
        name = pardata['name']
        meta['_parameter_order'].append(name)

        #parse keywords (if there are any)
        if pardata['keywords'] is None:
            keywords = []
        else:
            keywords = re.findall(r'''("[^"]+"|'[^']+'|[^\s]+)''', pardata['keywords'])

        flags = []
        for kw in keywords:
            if '=' in kw:
                k, v = kw.split('=', 1)
                meta['_parameters'][name][k] = v.strip()
            else:
                flags.append(kw)

        meta['_parameters'][name]['flags'] = flags

    # once again - now remove all parameters
    rv =  re_find_param.sub("", src).strip()
    meta['_src'] = rv


def replace_params_one(meta):

    src = meta['_src']

    #print('-' * 80)
    for k in meta:
        if k[0] == '_': continue
        rex = r'{{\s*' + k + '\s*}}'
        find_k = re.compile(rex, re.M)
        src = find_k.sub(str(meta[k]), src)
    meta['_src'] = src
