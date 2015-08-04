

import kea2.log

lg = kea2.log.get_logger(__name__)

def gnu_parallel_executor():
    pass

def init(meta):
    lg.info("Initializing gnu parallel executor")
    meta['_executors']['gnu_parallel']['function'] = gnu_parallel_executor
