from datetime import datetime
import sys

DEBUG = False
LOGFILE = '/var/log/t128-interface-usage.log'

def log(*messages):
    """Write messages to log file."""
    with open(LOGFILE, 'a') as fd:
        fd.write('{:%Y-%m-%d %H:%M:%S UTC} | {}\n'.format(
            datetime.utcnow(), ' '.join(messages)))

def debug(*messages):
    """Show error message and quit."""
    if DEBUG:
        log('DEBUG:', *messages)

def fatal(*messages):
    """Show error message and quit."""
    log('FATAL:', *messages)
    sys.exit(1)

def info(*messages):
    """Show error message and quit."""
    log('INFO:', *messages)

def warning(*messages):
    """Show error message and quit."""
    log('WARNING:', *messages)
