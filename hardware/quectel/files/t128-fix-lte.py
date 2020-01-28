#!/usr/bin/env python
#
# This script shall be triggered by a cronjob in order to
# monitor LTE connection health.

from __future__ import print_function
from systemd import journal
import argparse
import fcntl
import os
import serial
import time

RESET_COUNTER_FILE = '/run/128technology/fix_lte_reset_counter'
DEBUG = False
DRY_RUN = False
INFO = False
QUIET = False


def parse_arguments():
    """Get commandline arguments."""
    parser = argparse.ArgumentParser(
        description='Check parameters of LTE modem and correct them if needed')
    parser.add_argument('--apn', help='custom APN', default='m2m.businessplus')
    parser.add_argument('--debug', help='print debug', action='store_true')
    parser.add_argument('--dry-run', action='store_true',
                        help='do not apply any changes')
    parser.add_argument('--ignore-apn', help='ignore APN', action='store_true')
    parser.add_argument('--info', help='print info', action='store_true')
    parser.add_argument('--quiet', help='be quiet', action='store_true')
    args = parser.parse_args()
    global DEBUG
    global DRY_RUN
    global INFO
    global QUIET
    DEBUG = args.debug
    DRY_RUN = args.dry_run
    INFO = args.info
    QUIET = args.quiet
    return args


def debug(message):
    """Print debug messages if requested."""
    if DEBUG:
        print('DEBUG:', message)


def error(message):
    """Print error messages if requested."""
    stream = journal.stream('fix_lte')
    print('ERROR:', message, file=stream)
    if not QUIET:
        print('ERROR:', message)


def info(message):
    """Print info messages if requested."""
    stream = journal.stream('fix_lte')
    print('INFO:', message, file=stream)
    if DEBUG or INFO:
        print('INFO:', message)


def seek_ec25():
    """Seek for Quectel LTE modem."""
    debug('Seeking EC25/EG25...')
    if os.system('lsusb | grep -q "ID 2c7c:0125"') != 0:
        error('No Quectel EC25/EG25 found. Exiting...')
        return False
    return True


def fix_apn(modem, apn):
    """Check and fix APN."""
    debug('Checking APN...')
    found_apn = False
    modem.write(b'AT+CGDCONT?\r')
    time.sleep(0.5)
    for i in range(10):
        data = modem.readline()
        debug(data.strip())
        if 'ERROR' in data:
            info('An Error has occurred. No SIM inserted?')
            return
        if apn in data:
            found_apn = True
        if data == 'OK\r\n':
            break
    if not found_apn:
        info('Expected APN not found. Replacing first APN profile...')
        if not DRY_RUN:
            modem.write(b'AT+CGDCONT=1,"IP","{}"\r'.format(apn))


def read_reset_counter():
    """Read reset counter from file for persistence across cronjobs."""
    debug('Reading reset counter...')
    reset_counter = 0
    try:
        with open(RESET_COUNTER_FILE) as fd:
            reset_counter = int(fd.read())
    except IOError:
        pass
    finally:
        return reset_counter


def write_reset_counter(reset_counter):
    """Write reset counter to file for persistence across cronjobs."""
    debug('Writing reset counter...')
    with open(RESET_COUNTER_FILE, 'w') as fd:
        fd.write('{}\n'.format(reset_counter))


def check_received_packets(modem):
    """Check if packets have been received during the last 5 minutes."""
    debug('Checking packet count...')
    reset_counter = read_reset_counter()
    if not os.system("test $(journalctl --since '5 minutes ago' -u 128T | grep 'RX packets OK: ' | awk '{$1=$1}1' | sort -u | wc -l) -gt 1") == 0:
        info("Resetting LTE modem...")
        write_reset_counter(reset_counter + 1)
        if not DRY_RUN:
            modem.write(b'AT+CFUN=1,1\r')
    else:
        write_reset_counter(0)


def main():
    args = parse_arguments()
    if not seek_ec25():
        return

    # open modem connection
    device_name = '/dev/ttyUSB2'
    lock_file = '/var/lock/{}.lock'.format(device_name.split('/')[-1])
    try:
        with open(lock_file, 'w') as fd:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        error('Could not acquire modem lock file.')
        return
    modem = serial.Serial(device_name, timeout=5)
    try:
        if not args.ignore_apn:
            fix_apn(modem, args.apn)
        check_received_packets(modem)
    finally:
        modem.close()


if __name__ == '__main__':
    main()
