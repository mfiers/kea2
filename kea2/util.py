
from collections import defaultdict
import functools
import glob
import logging
import os
import pkg_resources as pr
from pprint import pprint
import time


from jinja2 import Environment
from path import Path
from sh import git, ErrorReturnCode
import yaml

import kea2.log

lg = kea2.log.get_logger(__name__, 'warning')

def _make_dict():
    return defaultdict(_make_dict)

def get_recursive_dict():
    return defaultdict(_make_dict)


HOOKS = get_recursive_dict()
CONF = None

def getconf():
    global CONF

    if not CONF is None:
        return CONF

    CONF = get_recursive_dict()

    resname = 'etc/config/k2rc'
    if pr.resource_exists('kea2', resname):
        CONF.update(yaml.load(pr.resource_string('kea2', resname).decode('UTF-8')))

    conf_file = Path('~/.k2rc').expanduser()
    if conf_file.exists():
        with open(conf_file, 'r') as F:
            CONF.update(yaml.load(F))

    return CONF

#
# Extra Jinja filters
#

def _jinja_filter_basename(fn, extension=None):
    rv = os.path.basename(fn)
    extension = extension.strip()
    if not extension is None and rv.endswith(extension):
        rv = rv[:-len(extension)]
    return rv


def recursive_render(tmpl, data):
    last_out = False
    while True:
        out = tmpl.render(data)
        if (not last_out is False) and (last_out == out):
            break
        tmpl = get_jinja_environment().from_string(out)
        last_out = out
    return out


def register_jinja2_filters(jenv):
    jenv.filters['basename'] = _jinja_filter_basename


@functools.lru_cache(1)
def get_jinja_environment():
    jenv = Environment()
    register_jinja2_filters(jenv)
    return jenv


def script_write(script, dirname, uid, backup_dir=None):

    dirname = Path(dirname)
    if backup_dir is None:
        backup_dir = dirname /  'backup'
    else:
        backup_dir = Path(backup_dir)

    if uid:
        cmd_file = dirname / ('kea2.%s.sh' % uid)
    else:
        cmd_file = dirname / 'kea2.sh'

    if not dirname.exists():
        os.makedirs(dirname)

    try:
        output = git('rev-parse')
        ingit = True
        lg.debug("In a git repository - add & commit the script")
    except ErrorReturnCode as e:
        lg.info("not git - backing up the cmd file")
        ingit = False

    if cmd_file.exists():
        #check if in git:
        if ingit:
            for line in git.status('-s', cmd_file):
                _status, _filename = line.strip().split(None, 1)
                lg.warning('git status prewrite: %s %s', _status, _filename)
                if _filename != cmd_file:
                    lg.warning("this is not the file we want: %s", _filename)
                    continue
                if _status == '??':
                    git.add(cmd_file)
                if _status in ['??', 'A', 'M']:
                    lg.warning("git commit old version of %s", cmd_file)
                    git.commit(cmd_file, m='autocommit by kea2 - prepare for new version')
        else:
            #not in a git repository - copy file to a temp file
            ocf_stat = cmd_file.stat()
            timestamp = time.strftime("%Y-%m-%d_%H:%M:%S",
                                      time.localtime(ocf_stat.st_ctime))
            if not backup_dir.exists():
                os.makedirs(backup_dir)
            new_file_name = backup_dir / ('_kea2.%s.%s.sh' % (uid, timestamp))
            lg.info("rename old %s to %s", cmd_file, new_file_name)
            cmd_file.move(new_file_name)

    script = script.rstrip()
    with open(cmd_file, 'w') as F:
        F.write(script)
        F.write('\n')
    cmd_file.chmod('a+x')
    return cmd_file


#
# Templates
#

def get_template(meta, name, category='template'):

    template_path = Path(name)
    if template_path.exists():
        with open(name, 'r') as F:
            src = F.read().strip()
            return src

    if (template_path + '.k2').exists():
        with open((template_path + '.k2'), 'r') as F:
            src = F.read().strip()
            return src

    if 'templates' in meta['_conf']:
        tconf =  meta['_conf']['templates']
    else:
        tconf = [{'user': '~/kea2'},
                 {'system': '/etc/kea2'} ]


    for tdict in tconf:
        assert len(tdict) == 1
        tname, tpath = list(tdict.items())[0]
        tpath = Path(tpath).expanduser()

        lg.debug('check template set "%s" @ %s', tname, tpath)

        template_folder = tpath / category

        lg.debug("check for template in: %s", template_folder)

        template_file_1 = Path('{}/{}'.format(template_folder, name))\
          .expanduser()
        template_file_2 = Path('{}/{}.k2'.format(template_folder, name))\
          .expanduser()

        if  template_file_1.exists():
            lg.debug('loading template for "%s" from "%s"', name, template_file_1)
            with open(template_file_1, 'r') as F:
                return F.read()

        if  template_file_2.exists():
            lg.debug('loading template for "%s" from "%s"', name, template_file_2)
            with open(template_file_2, 'r') as F:
                return F.read()

        # template was not found -- continue
        lg.debug('cannot find template "%s" here', name)

    #still no template - check package resources
    resname1 = 'etc//%s/%s' % (category, name)
    resname2 = 'etc//%s/%s.k2' % (category, name)

    lg.debug("check package resources @ %s", resname1)
    if pr.resource_exists('kea2', resname1):
        return pr.resource_string('kea2', resname1).decode('UTF-8')
    if pr.resource_exists('kea2', resname2):
        return pr.resource_string('kea2', resname2).decode('UTF-8')


    #nothing - quit!
    lg.critical('cannot find template: "%s"', name)
    exit(-1)





def get_jinja_template(meta, name, location):
    template = get_template(meta, name, location)
    jenv = get_jinja_environment()
    return jenv.from_string(template)



def list_templates(meta, category='template'):

    for locfile in glob.glob('*.k2'):
        yield 'local', locfile

    if 'templates' in meta['_conf']:
        tconf =  meta['_conf']['templates']
    else:
        tconf = [{'user': '~/kea2'},
                 {'system': '/etc/kea2'} ]

    for tdict in tconf:
        assert len(tdict) == 1
        tname, tpath = list(tdict.items())[0]
        tpath = Path(tpath).expanduser()

        lg.debug('list templates "%s" @ %s', tname, tpath)

        template_folder = tpath / category

        for fn in glob.glob(template_folder / '*.k2'):
            fn = Path(fn).basename()
            yield tname, fn

    #list package resources
    resdir = 'etc/%s' % (category)
    lg.debug("list package resources from: %s", resdir)
    for fn in pr.resource_listdir('kea2', resdir):
        yield 'package', fn



def get_template_name(meta):

    template_name = getattr(meta['_args'], 'template', None)

    if not template_name is None:
        if '/' in template_name:
            template_name = template_name.split('/')[-1]
        if template_name.endswith('.k2'):
            template_name = template_name[:-3]
    else:
        ocl = meta.get('_original_commandline')
        if '--' in ocl:
            oen = ocl.split('--')[1].strip().split()[0]
            if '/' in oen:
                oen = oen.split('/')[-1]
            template_name = oen
        else:
            template_name = 'run'
    return template_name



#
# Plugins & Hooks
#

def register_command(meta, name, function):
    sp = meta['_kea2_subparser'].add_parser(name)
    meta['_subparsers'][name] = sp
    meta['_commands'][name] = function
    return sp

def load_plugins(meta, system):
    for plugin in list(meta['_conf'][system]):
        pdata = meta['_conf'][system][plugin]
        modname = pdata['module'] \
          if 'module' in pdata \
          else 'kea2.{}.{}'.format(system, plugin)
        module = __import__(modname, fromlist=[''])
        meta['_conf'][plugin]['_mod'] = module
        if hasattr(module, 'init'):
            module.init(meta)
        else:
            lg.warning("invalid plugin - no init function: %s", plugin)


def run_hook(hook_name, *args, **kwargs):

    to_run = sorted(HOOKS.get(hook_name, {}), key=lambda x: x[0])

    for order, function in to_run:
        lg.debug('executing hook %s:%s order: %s',
                 hook_name, function.__name__, order)

        try:
            function(*args, **kwargs)
        except TypeError:
            lg.critical('Error calling hook "%s" in %s',
                        hook_name, function.__name__)
            raise

def register_hook(hookname, function, order=50):
    lg.info('register hook "%s": %s"', hookname, function.__name__)
    if not hookname in HOOKS:
        HOOKS[hookname] = []
    HOOKS[hookname].append((order, function))
