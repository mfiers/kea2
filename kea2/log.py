
import logging
from colorlog import ColoredFormatter

color_formatter = ColoredFormatter(
        "%(log_color)s%(levelname)-8s%(reset)s %(blue)s%(message)s",
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

logging.basicConfig(level=logging.DEBUG)
logging.getLogger('k2')
logging.getLogger().handlers[0].setFormatter(color_formatter)

def get_logger(name):
    return logging.getLogger(name)
