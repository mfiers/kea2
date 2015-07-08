
import argparse
from collections import defaultdict
import copy
import glob
import os
import re
import shlex
import sys

from jinja2 import Template

from kea2 import render
from kea2.log import get_logger


def format_template(src):
    return " ".join(shlex.split(src))

lg = get_logger('k2')
#print(lg.handlers)

def _get_base_argsparse():
    parser = argparse.ArgumentParser()
    parser.add_argument('--parse-level', type=int, default=2)
    parser.add_argument('-x', '--executor', default='gnu_parallel')
    parser.add_argument('template')
    return parser

def _get_template(name):
    if os.path.exists(name):
        with open(name, 'r') as F:
            src = F.read().strip()

    template_dir = os.path

def _phase_one(meta):
    """ Identify command line parameters """
    lg.debug('Start phase one')
    sysargs = copy.copy(sys.argv[1:])
    #do not show help here yet
    while '-h' in sysargs:
        sysargs.remove('-h')
    while '--help' in sysargs:
        sysargs.remove('--help')

    parser = _get_base_argsparse()
    args, rest = parser.parse_known_args(sysargs)

    src = _get_template(args.template)

    if args.parse_level == 0:
        print(format_template(src))
        exit(0)

    new_src = render.find_params(src, meta)

    if args.parse_level == 1:
        print('template', '-' * 50)
        print(new_src)
        print('parameters', '-' * 48)
        for p, pdata in sorted(meta['_parameters'].items()):
            print('{}\t{}'.format(
                p,
                pdata.get('help', ''),))
        print('-' * 59)
        exit(0)

    return new_src

def _parameter_replace(src, meta):
    """ Parser command line & replace parameters """
    lg.debug('Start phase two')

    parser = _get_base_argsparse()

    for p, pdata in sorted(meta['_parameters'].items()):

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

        if 'opt' in pdata['flags']:
            pname = '--' + p
        else:
            pname = p

        parser.add_argument(pname, type=ptype, help=phelp, default=pdef)

    args = parser.parse_args()

    #now parse arguments - and populate meta
    for p, pdata in meta['_parameters'].items():
        val = getattr(args, p)
        meta[p] = val

    #first round of value replacement
    return render.replace_params_one(src, meta)

def _expander(src, meta):
    """
    prepare for globification
    """

    #check shortcut(s)
    find_glob_shortcut = re.compile('(?<!{){\s*\*\s*}(?!})')
    no_glob_shortcuts = len(find_glob_shortcut.findall(src))
    if no_glob_shortcuts > 1:
        lg.critical("invalid template: >1 {*}")
    elif no_glob_shortcuts == 1:
        src = find_glob_shortcut.sub('{~star *}', src)
        src = re.sub('{{\s*\*\s*}}', '{{ star }}', src)


    #globify
    find_glob = re.compile((r'(?<!{){'
                            r'(?P<operator>~)'
                            r'(?P<name>[a-zA-Z]\w*) '
                            r'(?P<pattern>[^}]+)'
                            r'\s*}(?!})'))


    def globulator(src, meta, hit):

        hitstart = hit.start()
        hitstop = hit.end()

        #random, hopefully unique, replacement string that we can retrieve
        rnd = 'QqZzRrHhGgTtUuVvWw'
        repl_str = (rnd * (int((hitstop - hitstart) / len(rnd)) + 2))[:hitstop-hitstart]

        src_repl = src[:hitstart] + repl_str + src[hitstop:]
        for srcword in shlex.split(src_repl):
            if repl_str in srcword:
                break

        globword = srcword.replace(repl_str, hit.groupdict()['pattern'])

        glob_start = srcword.index(repl_str)
        glob_tail = len(srcword) - (srcword.index(repl_str) + len(repl_str))
        for g in glob.glob(globword):
            newsrc = src_repl.replace(repl_str, g)
            newmeta = copy.copy(meta)

            repl_glob = srcword.index(repl_str)
            gg = copy.copy(g)
            gg = gg[:-glob_tail]
            gg = gg[glob_start:]

            newmeta[hit.groupdict()['name']] = gg
            yield newsrc, newmeta

    def _expander(src, meta):
        hit = find_glob.search(src)
        if not hit:
            yield src, meta
            return

        d = hit.groupdict()
        if d['operator'] == '~':
            for nsrc, nmeta in globulator(src, meta, hit):
                for nnsrc, nnmeta in _expander(nsrc, nmeta):
                    yield nnsrc, nnmeta

    for i, (s, m) in enumerate(_expander(src, meta)):
        m['i'] = i
        t = Template(s)
        s = t.render(m)
        s = " ".join(shlex.split(s))
        yield s, m


GNU_PARALLEL_CMD_SCRIPT = Template("""
echo {{ cmdlist }} | parallel

""")

GNU_PARALLEL_CMD_LIST = Template(
"""
{% for cmd, meta in commands %}
{{ cmd }}{% endfor %}
""")


def k2():
    lg.info("Start k2")

    def make_dict():
        return defaultdict(make_dict)
    meta = defaultdict(make_dict)

    src = _phase_one(meta)
    src = _parameter_replace(src, meta)
    commands = []
    for src, meta in _expander(src, meta):
        commands.append((src, meta))

    cmdlist_file = 'commands.list'
    cmd_file = 'k2run.sh'

    clist = GNU_PARALLEL_CMD_LIST.render(
        dict(commands = commands))
    cmd = GNU_PARALLEL_CMD_SCRIPT.render(
        dict(cmdlist = cmdlist_file))

    with open(cmdlist_file, 'w') as F:
        F.write(clist)
    with open(cmd_file, 'w') as F:
        F.write(cmd)
        F.write("\n")
