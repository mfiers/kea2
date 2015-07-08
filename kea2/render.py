
from logging import INFO
import re
import shlex

from kea2.log import get_logger

lg = get_logger('k2.render')
lg.setLevel(INFO)

re_find_param_r = (
    r'#p\s+'
    r'(?P<name>[A-Za-z][A-Za-z0-9_]*)'
    r'(\s+(?P<keywords>[^\n]+))?'
    r'\n')

re_find_param = re.compile(re_find_param_r, re.M)

ALLOWED_PARAMETER_FLAGS = """
    opt
    int float
    hide
""".split()

def find_params(src, meta):
    lg.debug("Start render level 01")

    for hit in re_find_param.finditer(src):
        pardata = hit.groupdict()
        name = pardata['name']

        #parse keywords (if there are any)
        if pardata['keywords'] is None:
            keywords = []
        else:
            keywords = shlex.split(pardata['keywords'])

        flags = []
        for kw in keywords:
            if '=' in kw:
                k, v = kw.split('=', 1)
                meta['_parameters'][name][k] = v.strip()
            else:
                flags.append(kw)

        meta['_parameters'][name]['flags'] = flags

    # once again - now remove all parameters
    return re_find_param.sub("", src).strip()

def replace_params_one(src, meta):
    #print(src)
    #print('-' * 80)
    for k in meta:
        if k[0] == '_': continue
        rex = r'{{\s*' + k + '\s*}}'
        find_k = re.compile(rex, re.M)
        src = find_k.sub(str(meta[k]), src)
        #print('#####', k, meta[k], rex)
        #print(src)
        #print('-' * 80)
    return src
