
import logging
import os
import sys

from colorlog import ColoredFormatter

color_formatter = ColoredFormatter(
        "%(log_color)sk2%(reset)s %(message)s",
        datefmt=None,
        reset=True,
        log_colors={
                'DEBUG':    'cyan',
                'INFO':     'green',
                'WARNING':  'yellow',
                'ERROR':    'red',
                'CRITICAL': 'red',
        }
)

logging.basicConfig(level=logging.WARNING)
logging.getLogger('k2')

if os.isatty(sys.stderr.fileno()):
    logging.getLogger().handlers[0].setFormatter(color_formatter)

def get_logger(name, level=None):
    rv = logging.getLogger(name)
    if not level is None:
        if isinstance(level, str):
            rv.setLevel(dict(
                debug=logging.DEBUG,
                info=logging.INFO,
                warning=logging.WARNING)[level])
        else:
            rv.setLevel(level)
    return rv
