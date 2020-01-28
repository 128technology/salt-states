#!/usr/bin/env python
#
# This script locks the modem for a given timeout and allows maintenance

from __future__ import print_function
import argparse
import fcntl
import time


def parse_arguments():
    """Get commandline arguments."""
    parser = argparse.ArgumentParser(
        description='Locks an UMTS/LTE modem for a given timeout.')
    parser.add_argument('--modem', '-m', default='/dev/ttyUSB2',
                        help='Location of UMTS/LTE device file')
    parser.add_argument('timeout', help='Timeout in seconds', type=int)
    args = parser.parse_args()
    return args


def main():
    args = parse_arguments()
    lock_file = '/var/lock/{}.lock'.format(args.modem.split('/')[-1])
    try:
        with open(lock_file, 'w') as fd:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            time.sleep(args.timeout)
    except IOError:
        print('Could not acquire modem lock file.')
        return


if __name__ == '__main__':
    main()
