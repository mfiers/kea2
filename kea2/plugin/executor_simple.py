
from hashlib import sha1
import os
from pprint import pprint
import subprocess as sp
import time


from jinja2 import Environment, FileSystemLoader, Template
from path import Path
from sh import git, ErrorReturnCode
import sh

import kea2.log
from kea2.util import register_hook
from kea2 import util


lg = kea2.log.get_logger(__name__)

EXECLIST = []
GLOBALHASH = sha1()
CMD_FILE = None

def to_execute(meta):
    lg.debug("register for execution")
    global EXECLIST
    EXECLIST.append(meta)


def pre_execute():

    global EXECLIST
    global CMD_FILE

    if len(EXECLIST) == 0:
        #nothing to do
        lg.warning("nothing to execute")
        exit(-1)

    conf = util.getconf()
    lg.debug("no commands to executed: %d", len(EXECLIST))

    tmpl_path = Path('~/kea2/executor/simple/').expanduser()
    lg.debug("load templates from: %s", tmpl_path)

    jenv = Environment(loader=FileSystemLoader(tmpl_path))
    util.register_jinja2_filters(jenv)

    cmdlist = []

    global_meta = EXECLIST[0]['_global_meta']

    for meta in EXECLIST:
        src = meta['_src']
        meta['command'] = src
        #if meta['i'] == 0:
        #    pprint(meta)

        cmd = jenv.get_template('command.template').render(meta)
        cmdlist.append(cmd)


    global_meta['commandlist'] = cmdlist

    template_name = util.get_template_name(global_meta)

    CMD_FILE = Path('{}.sh'.format(template_name))


    if CMD_FILE.exists():
        #check if in git:

        try:
            output = git('rev-parse')
            ingit = True
            lg.debug("In a git repository - add & commit the script")
        except ErrorReturnCode as e:
            lg.warning("not git - backing up the cmd file")
            ingit = False


        if ingit:
            for line in git.status('-s', CMD_FILE):
                _status, _filename = line.strip().split(None, 1)
                lg.warning('git status prewrite: %s %s', _status, _filename)
                if _filename != CMD_FILE:
                    lg.warning("this is not the file we want: %s", _filename)
                    continue
                if _status == '??':
                    git.add(CMD_FILE)
                if _status in ['??', 'A', 'M']:
                    lg.warning("git commit old version of %s", CMD_FILE)
                    git.commit(CMD_FILE, m='autocommit by kea2 - prepare for new version')
        else:
            #not in a git repository - copy file to a temp file
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
    if ingit:
        lg.debug("commit latest version of %s to git", CMD_FILE)
        git.commit(CMD_FILE, m='new kea2 generation')


def execute():
    global CMD_FILE
    if CMD_FILE is None:
        lg.crticial("cmd script is not defined")
        exit(-1)
    CMD_FILE = CMD_FILE.abspath()
    lg.info('executing: "%s"', CMD_FILE)
    rc = sp.call([CMD_FILE])
    if rc == 0:
        lg.info('finshed sucessfully')
    else:
        lg.warning('Error running script, rc: %s', rc)


def init(meta):
    lg.debug("Initializing gnu parallel executor")
    register_hook('to_execute', to_execute)
    register_hook('pre_execute', pre_execute)
    register_hook('execute', execute)
