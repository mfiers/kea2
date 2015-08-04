
from hashlib import sha1
import os
from pprint import pprint
import subprocess as sp
import time

from jinja2 import Environment, FileSystemLoader, Template
from path import Path

import kea2.log
from kea2.util import register_hook
from kea2 import util


lg = kea2.log.get_logger(__name__)

EXECLIST = []
GLOBALHASH = sha1()
CMD_FILE = None

def gnu_parallel_executor():
    script_file = script_path / Path('{}.sh'.format(digest))
    with open(script_file, 'w') as F:
        F.write(src)
        F.write("\n")
    commands.append((script_file, meta))
    script_file.chmod('u+x')

def to_execute(meta):
    lg.debug("register for execution")
    global EXECLIST
    global GLOBALHASH

    src = meta['_src']

    hash = sha1()
    GLOBALHASH.update(src.encode('UTF-8'))
    hash.update(src.encode('UTF-8'))
    meta['_digest'] = hash.hexdigest()[:9]
    EXECLIST.append(meta)


def pre_execute():

    global EXECLIST
    global GLOBALHASH
    global CMD_FILE

    if len(EXECLIST) == 0:
        #nothing to do
        lg.warning("nothing to execute")
        exit(-1)


    script_path = Path('./kea2/')
    if not script_path.exists():
        os.makedirs(script_path)
    lg.debug("writing command scripts to: %s", script_path)


    conf = util.getconf()
    lg.debug("commands to executed: %d", len(EXECLIST))


    tmpl_path = Path('~/kea2/executor/gnu_parallel/').expanduser()
    lg.debug("load templates from: %s", tmpl_path)
    jenv = Environment(loader=FileSystemLoader(tmpl_path))

    commandlist = []
    listdigest = sha1()

    global_meta = EXECLIST[0]['_global_meta']

    for meta in EXECLIST:
        src = meta['_src']
        meta['command'] = src
        digest = meta['_digest']
        listdigest.update(digest.encode('UTF-8'))
        script_file = script_path / Path('k2.{}.sh'.format(digest))
        lg.debug("script: %s", script_file)

        commandlist.append(script_file)
        with open(script_file, 'w') as F:
            cmd = jenv.get_template('command.template').render(meta)
            F.write(cmd)
        script_file.chmod('u+rx')

    listdigest = listdigest.hexdigest()[:9]
    lg.debug("list digest: %s", listdigest)

    global_meta['commandlist'] = commandlist

    template_name = util.get_template_name(global_meta)

    CMD_FILE = Path('{}.sh'.format(template_name))
    if CMD_FILE.exists():
        ocf_stat = CMD_FILE.stat()
        timestamp = time.strftime("%Y-%m-%d_%H:%M:%S",
                                  time.localtime(ocf_stat.st_ctime))
        new_file_name = '_{}_{}.sh'.format(template_name, timestamp)
        lg.info("rename old %s to %s", CMD_FILE, new_file_name)
        CMD_FILE.move(new_file_name)

    runsh = jenv.get_template('run.template').render(global_meta)

    lg.info("write command script: %s", CMD_FILE)
    with open(CMD_FILE, 'w') as F:
        F.write(runsh)
        F.write("\n")

    CMD_FILE.chmod('a+x')

def execute():
    global CMD_FILE
    if CMD_FILE is None:
        lg.crticial("cmd script is not defined")
        exit(-1)
    rc = sp.call([CMD_FILE])
    lg.warning('rc: %s', rc)

def init(meta):
    lg.debug("Initializing gnu parallel executor")
    register_hook('to_execute', to_execute)
    register_hook('pre_execute', pre_execute)
    register_hook('execute', execute)
