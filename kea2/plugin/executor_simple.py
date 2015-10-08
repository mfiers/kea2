
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

    lg.debug("number of commands to execute: %d", len(EXECLIST))

    cmdlist = []
    global_meta = EXECLIST[0]['_global_meta']
    template_name = util.get_template_name(global_meta)

    for i, meta in enumerate(EXECLIST):
        cmd = util.get_jinja_template(meta, 'command.template', 'executor/simple')
        cmd = util.recursive_render(cmd, meta)
        meta['_cmd_file'] = util.script_write(cmd, './kea2', meta['_uid'])
        cmdrunner = util.get_jinja_template(meta, 'command_runner.template', 'executor/simple')
        cmdrunner = util.recursive_render(cmdrunner, meta)
        cmdlist.append(cmdrunner)

    global_meta['commandlist'] = cmdlist

    try:
        output = git('rev-parse')
        ingit = True
        lg.debug("In a git repository - add & commit the script")
    except ErrorReturnCode as e:
        lg.info("not git - backing up the cmd file")
        ingit = False

    runsh = util.get_jinja_template(meta, 'run.template', 'executor/simple').render(global_meta)

    cmd_file = template_name
    lg.info("write command script: %s", CMD_FILE)
    util.script_write(runsh, '.', template_name, backup_dir='./kea2/backup')



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
