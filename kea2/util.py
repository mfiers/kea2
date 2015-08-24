
from collections import defaultdict
import glob
import logging
import os
from pprint import pprint

import pkg_resources as pr



from path import Path
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


def register_jinja2_filters(jenv):
    jenv.filters['basename'] = _jinja_filter_basename


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

        template_file = Path('{}/{}.k2'.format(template_folder, name))\
          .expanduser()

        print(template_file)
        if  template_file.exists():
            lg.debug('loading template for "%s" from "%s"', name, template_file)
            with open(template_file, 'r') as F:
                return F.read()

        # template was not found -- continue
        lg.debug('cannot find template "%s" here', name)

    #still no template - check package resources
    resname = 'etc//%s/%s.k2' % (category, name)
    lg.debug("check package resources @ %s", resname)
    if not pr.resource_exists('kea2', resname):
        #nothing - quit!
        lg.critical('cannot find template: "%s"', name)
        exit(-1)

    #read & return
    return pr.resource_string('kea2', resname).decode('UTF-8')


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
