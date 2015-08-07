 
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

import yaml
from path import Path

from jinja2 import Template

from kea2 import render
from kea2.log import get_logger
from kea2.util import run_hook, register_hook, get_recursive_dict
from kea2 import util

lg = get_logger('k2', 'warning')


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


def parameter_replace(meta):
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
        meta[p] = val

    #first round of value replacement
    render.replace_params_one(meta)

def expander(meta):
    """
    prepare for globification
    """

    src = meta['_src']

    #check shortcut(s)
    find_glob_shortcut = re.compile('(?<!{){\s*\*\s*}(?!})')
    no_glob_shortcuts = len(find_glob_shortcut.findall(src))

    if no_glob_shortcuts > 1:
        lg.critical("invalid template: >1 {*}")
    elif no_glob_shortcuts == 1:
        src = find_glob_shortcut.sub('{~star *}', src)
        src = re.sub('{{\s*\*\s*}}', '{{ star }}', src)

    meta['_src'] = src

    #globify
    find_glob = re.compile((r'(?<!{){'
                            r'(?P<operator>~)'
                            r'(?P<name>[a-zA-Z]\w*) '
                            r'(?P<pattern>[^}]+)'
                            r'\s*}(?!})'))

    def globulator(meta, hit):

        src = meta['_src']
        hitstart = hit.start()
        hitstop = hit.end()

        #random, hopefully unique, replacement string that we can retrieve
        rnd = 'QqZzRrHhGgTtUuVvWw'
        repl_str = (rnd * (int((hitstop - hitstart) / len(rnd)) + 2))[:hitstop-hitstart]

        src_repl = src[:hitstart] + repl_str + src[hitstop:]
        for srcword in shlex.split(src_repl):
            srcword = srcword.rstrip(';')
            if repl_str in srcword:
                break

        globword = srcword.replace(repl_str, hit.groupdict()['pattern'])
        glob_start = srcword.index(repl_str)
        glob_tail = len(srcword) - (srcword.index(repl_str) + len(repl_str))

        lg.debug("glob: %s", globword)
        for g in glob.glob(globword):

            lg.debug("glob found: %s", g)
            newsrc = src_repl.replace(srcword, g)
            newmeta = copy.copy(meta)

            repl_glob = srcword.index(repl_str)
            gg = copy.copy(g)
            gg = gg[:-glob_tail]
            gg = gg[glob_start:]

            newmeta[hit.groupdict()['name']] = gg
            newmeta['_src'] = newsrc
            yield newmeta

    def _expander(meta):
        src = meta['_src']

#        import logging
#        lg.setLevel(logging.DEBUG)
        lg.debug('expand: %s', src)

        hit = find_glob.search(src)
        if not hit:
            yield meta
            return

        d = hit.groupdict()
        lg.debug("Expanding: %s %s %s", d['operator'], d['name'], d['pattern'])
        if d['operator'] == '~':
            for n_meta in globulator(meta, hit):
                for nn_meta in _expander(n_meta):
                    yield nn_meta

    for i, _meta in enumerate(_expander(meta)):
        _meta['i'] = i
        template = Template(_meta['_src'])
        _meta['_src'] = template.render(_dictify(_meta))
        yield _meta


def template_splitter(meta):

    template = meta['_src']

    inblock = None
    main = None
    thisblock = []
    seen = set()

    lg.debug("Start template split")
    for line in template.split("\n"):
        if re.match('^###\s*[a-zA-Z_]+$', line):
            if len(thisblock) > 0:
                if inblock is None:
                    lg.critical("code prior to blockheader in template")
                    exit(-1)

                meta['_blocks'][inblock] = "\n".join(thisblock)
                seen.add(inblock)

            block = line.strip().strip("#").strip()
            inblock = block
            thisblock = []
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

    meta['_commands'][command](meta)
    
#    if args.command == 'list':
#        k2m_list(argsa)

    

def k2():

    def make_dict():
        return defaultdict(make_dict)

    meta = get_recursive_dict()
    meta['_conf'] = util.getconf()
    meta['_original_commandline'] = " ".join(sys.argv)

    util.load_plugins(meta, 'plugin')
    
    # for plugin in list(meta['_conf']['plugin']):
    #     pdata = meta['_conf']['plugin'][plugin]
    #     modname = pdata['module'] if 'module' in pdata \
    #               else 'kea2.plugin.{}'.format(plugin)
    #     module = __import__(modname, fromlist=[''])
    #     meta['_conf'][plugin]['_mod'] = module
    #     if hasattr(module, 'init'):
    #         module.init(meta)
    #     else:
    #         lg.warning("invalid plugin - no init function: %s", plugin)

    # Phase one - PREPARG - preparse arguments
    phase_one(meta)

    # Load executor
    executor = meta['_preargs'].executor
    lg.info("Executor: %s", executor)
    edata = meta['_conf']['executor'][executor]
    modname = edata['module']
    module = __import__(modname, fromlist=[''])
    meta['_conf'][executor]['_mod'] = module
    module.init(meta)

    # Phase two - REPLARG - replace arguments
    parameter_replace(meta)

    # Phase three - SPLIT - split up the template into a main component
    template_splitter(meta)

    commands = []

    # Phase four - EXPAND - expand templates
    run_hook('pre_expand', meta)

    global_meta = meta.copy()
    meta['_global_meta'] = global_meta

    for meta in expander(meta):
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
