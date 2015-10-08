
import argparse
from collections import defaultdict
import copy
import glob
from hashlib import sha1
import os
from pprint import pprint
import re
import shlex
import sys
import uuid

import yaml
from path import Path

from jinja2 import Environment

from kea2 import render
from kea2.log import get_logger
from kea2.util import run_hook, register_hook, get_recursive_dict
from kea2 import util

lg = get_logger('k2', 'warning')

JENV = Environment()
util.register_jinja2_filters(JENV)


def _get_base_argsparse(add_template=True):
    parser = argparse.ArgumentParser()
    parser.add_argument('-x', '--executor', default='simple')
    parser.add_argument('-X', '--execute', action='store_const', help='run immediately',
                        const='run', dest='execute')
    parser.add_argument('-N', '--do-not-execute', action='store_const', help='do not run',
                        const='notrun', dest='execute')

    #register shortcuts to executors
    cnf = util.getconf()
    for xname, xconf in cnf['executor'].items():
        altflag = xconf.get('altflag')
        if altflag is None:
            continue

        parser.add_argument('--' + altflag, dest='executor', action='store_const',
                            const=xname, help='use %s executor' % xname)
    if add_template:
        parser.add_argument('template')
    return parser


def _simplistic_parse(add_template):
    parser = _get_base_argsparse(add_template=add_template)
    sysargs = copy.copy(sys.argv[1:])

    while '-h' in sysargs:
        sysargs.remove('-h')
    while '--help' in sysargs:
        sysargs.remove('--help')

    args, rest = parser.parse_known_args(sysargs)
    return args

def phase_one(meta):

    """ Identify command line parameters """
    lg.debug('Start phase one')


    if '--' in sys.argv:
        meta['_src_in_argv'] = True
        dd_index = sys.argv.index('--')
        meta['_src'] = " ".join(sys.argv[dd_index+1:])
        sys.argv = sys.argv[:dd_index]
        args = _simplistic_parse(add_template=False)
    else:
        meta['_src_in_argv'] = False
        args = _simplistic_parse(add_template=True)
        lg.info('template name: %s', args.template)
        meta['_src'] = util.get_template(meta, args.template)

    meta['_preargs'] = args
    render.find_params(meta)

def _dictify(d):
    for k, v in d.items():
        if isinstance(v, defaultdict):
            d[k] = _dictify(v)
    return dict(d)


def parameter_parse(meta):
    """ Parser command line & replace parameters """
    lg.debug('Start phase two')

    src = meta['_src']

    if meta['_src_in_argv']:
        parser = _get_base_argsparse(add_template=False)
    else:
        parser = _get_base_argsparse(add_template=True)


    for p in meta['_parameter_order']:

        pdata = meta['_parameters'][p]

        phelp = pdata.get('help', '')

        pdef = pdata.get('default', '').strip()

        if 'int' in pdata['flags']:
            ptype = int
            if pdef:
                pdef = int(pdef)
        elif 'float' in pdata['flags']:
            ptype = float
            pdef = float(pdef)
        else:
            ptype = str

        if pdef:
            phelp += ' default: {}'.format(pdef)

        pf = copy.copy(pdata['flags'])
        while 'opt' in pf:
            pf.remove('opt')
        if pf:
            phelp += ' ({})'.format(' '.join(pf))

        if 'opt' in pdata['flags'] or pdef:
            pname = '--' + p
        else:
            pname = p

        pkwargs = {}
        if 'multi' in pdata['flags']:
            pkwargs['nargs'] = '+'

        parser.add_argument(pname, type=ptype, help=phelp, default=pdef,
                            **pkwargs)

    args = parser.parse_args()
    meta['_args'] = args

    #now parse arguments - and populate meta
    for p, pdata in meta['_parameters'].items():
        val = getattr(args, p)
        pval = parameter_expander(p, val)
        if isinstance(pval, list):
            if not '_expanded_parameters' in meta:
                meta['_expanded_parameters'] = []
            meta['_expanded_parameters'].append(p)
        meta[p] = pval

def parameter_expander(pname, value):
    """

    """

    re_parfind = re.compile('(?<!\{)\{\s*\*\s*([A-Za-z_]\w*)?\s*\}(?!\})')

    mtch = re_parfind.search(str(value))
    if mtch is None:
        return value

    value = str(value)
    globpat = re_parfind.sub('*', value)
    assert re_parfind.search(globpat) is None
    replac = glob.glob(globpat)

    cutright = len(value) - mtch.end()
    cutleft = mtch.start()
    def pm(r):
        _t = {pname: r}
        name = mtch.groups()[0]
        if name is None:
            name = 'g'
        _t[name] = r[cutleft:-cutright]
        return _t

    return [pm(x) for x in replac]



def template_splitter(meta):

    template = meta['_src']

    inblock = None
    main = None
    thisblock = []
    seen = set()

    lg.debug("Start template split")
    for i, line in enumerate(template.split("\n")):
        if re.match('^###\s*[a-zA-Z_]+$', line):
            if len(thisblock) > 0:
                if inblock is None:
                    print(thisblock)
                    lg.critical("code prior to blockheader in template")
                    exit(-1)

                meta['_blocks'][inblock] = "\n".join(thisblock)
                seen.add(inblock)

            block = line.strip().strip("#").strip()
            inblock = block
            thisblock = []
        else:
            if i == 0 and line[:2] == '#!':
                #ignore shebang
                continue
            elif line.strip() == '':
                #ignore empty lines
                continue
            else:
                thisblock.append(line)

    if (not inblock is None) and len(thisblock) > 0:
        meta['_blocks'][inblock] = "\n".join(thisblock)
        seen.add(inblock)

    if len(seen) == 0:
        meta['_blocks']['main'] = template
        return template

    if not 'main' in seen:
        lg.critical("no main block in temlate found")
        exit(-1)

    # put the main block back into _src for postprocesing
    meta['_src'] = meta['_blocks']['main']


def k2_manage():
    """
    Manage k2
    """

    meta = get_recursive_dict()
    meta['_conf'] = util.getconf()
    meta['_parser'] = argparse.ArgumentParser()
    meta['_kea2_subparser'] = meta['_parser'].add_subparsers(dest='command')

    util.load_plugins(meta, 'manage_plugin')

    meta['_args'] = meta['_parser'].parse_args()
    command = meta['_args'].command

    if command is None:
        meta['_parser'].print_help()
        exit()

    #RUN
    meta['_commands'][command](meta)


def k2():

    meta = get_recursive_dict()
    meta['_conf'] = util.getconf()
    meta['_original_commandline'] = " ".join(sys.argv)

    util.load_plugins(meta, 'plugin')

    # Phase one - PREPARG - preparse arguments
    phase_one(meta)

    # Load proper executor
    executor = meta['_preargs'].executor
    lg.info("Executor: %s", executor)
    edata = meta['_conf']['executor'][executor]
    modname = edata['module']
    try:
        module = __import__(modname, fromlist=[''])
    except:
        lg.critical("error importing module %s", modname)
        lg.critical("executor conf: %s", str(meta['_conf']['executor']))
        raise
    meta['_conf'][executor]['_mod'] = module
    module.init(meta)

    # Phase two - parse command line parameters
    parameter_parse(meta)

    # Phase three - split templates in prolog, epilogs & main
    template_splitter(meta)

    global_meta = meta.copy()
    meta['_global_meta'] = global_meta

    # Phase three - expand templates
    run_hook('pre_expand', meta)

    def expander(meta):
        for pname, pdata in meta['_parameters'].items():
            pvalue = meta[pname]
            if isinstance(pvalue, list) and not 'multi' in pdata['flags']:
                for pvar in pvalue:
                    assert isinstance(pvar, dict)
                    meta = copy.copy(meta)
                    meta.update(pvar)
                    yield from expander(meta)
                break
        else:
            uid = ''
            if meta['_expanded_parameters']:
                ep = sorted(meta['_expanded_parameters'])
                def _fix(v):
                    if v.startswith('.'):
                        v = os.path.basename(v)
                    return v
                uid = "-".join([_fix(meta[x]) for x in ep]).replace(' ', '')
            meta['_uid'] = uid
            yield copy.copy(meta)


    for i, meta in enumerate(expander(meta)):
        meta['i'] = i

        meta['_blocks']['main'] = meta['_src']
        for bname, block in meta['_blocks'].items():
            try:
                template = JENV.from_string(block)
            except:
                lg.critical("Invalid Template in %s", bname)
                lg.critical(block)
                raise

            try:
                lastblock = False
                while (lastblock is None) or (lastblock != block):
                    lastblock = block
                    block = template.render(_dictify(meta))
                    template = JENV.from_string(block)
            except:
                lg.critical("Template render problem in %s", bname)
                lg.critical(block)
                raise
            meta['_blocks'][bname] = block
        meta['_src'] = meta['_blocks']['main']

        run_hook('check_execute', meta)

        if meta.get('_skip', False):
            lg.debug("skipping")
        else:
            run_hook('to_execute', meta)


    run_hook('pre_execute')

    if meta['_args'].execute == 'run' or \
      (global_meta.get('_src_in_argv') and not  global_meta['_args'].execute == 'notrun'):
        lg.info("start execution")
        run_hook('execute')


    run_hook('post_execute')
