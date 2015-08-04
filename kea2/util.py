
from collections import defaultdict
import logging
from pprint import pprint

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


def get_template(meta, name):

    template_path = Path(name)
    if template_path.exists():
        with open(name, 'r') as F:
            src = F.read().strip()
            return src

    template_folder = meta.get('template_folder')
    if not template_folder:
        template_folder = '~/kea2/template'

    lg.info("load template from: %s", template_folder)

    template_file = Path('{}/{}.k2'.format(template_folder, name))\
        .expanduser()

    if not template_file.exists():
        lg.critical("cannot find template (%s)", template_file)
        exit
    with open(template_file, 'r') as F:
        return F.read()

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
