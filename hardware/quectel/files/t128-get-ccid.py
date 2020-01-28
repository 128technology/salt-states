#!/usr/bin/env python

from __future__ import print_function
import fcntl
import json
import serial
import socket
import time


def main():
    try:
        with open("/etc/128technology/local.init") as fd:
            node = json.load(fd)["init"]["id"]
    except IOError:
        node = "unknown-node-name"

    hostname = socket.gethostname()

    # open modem connection
    device_name = '/dev/ttyUSB2'
    lock_file = '/var/lock/{}.lock'.format(device_name.split('/')[-1])
    try:
        with open(lock_file, 'w') as fd:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        print('ERROR: Could not acquire modem lock file.')
        return
    modem = serial.Serial(device_name, timeout=5)
    try:
        modem.write(b'AT+QCCID\r')
        time.sleep(0.5)
        for i in range(2):
            data = modem.readline()
            if '+QCCID:' in data:
                print("{},{},{}".format(
                    node,
                    hostname,
                    data.split()[1])
                )
    finally:
        modem.close()


if __name__ == '__main__':
    main()
