#!/usr/bin/env python

from __future__ import print_function
import json
import os
import smtplib
from subprocess import call, check_call, CalledProcessError
import sys
from time import ctime, strftime, time


TIMEOUT = 30
TEST_HOST = '1.1.1.1'
MAIL_ENABLED = False
STATE_FILE = '/run/128technology/icmp-healthcheck.json'
RESTART_CMD = '/usr/bin/systemctl restart 128T'
REBOOT_CMD = '/usr/sbin/reboot'
GLOBAL_INIT = '/etc/128technology/global.init'
PING_COMMAND = 'ping -q -c 4 -W 8'

basename = os.path.basename(__file__).replace('.py', '')


# Try to initiate function for systemd journal logging
try:
    from systemd import journal

    def log_journal(*messages):
        """Log messages to systemd journal."""
        stream = journal.stream(basename)
        print(*messages, file=stream)
except ModuleNotFoundError:
    def log_journal(*messages):
        """Log to stderr on systemd-free systems."""
        print(*messages, file=sys.stderr)

try:
    from subprocess import DEVNULL  # py3k
except ImportError:
    import os
    DEVNULL = open(os.devnull, 'wb')


def read_state(file_name=STATE_FILE):
    """Read previous state from file."""
    try:
        with open(file_name) as fd:
            return json.load(fd)
    except:
        return {'state': 'unknown'}


def write_state(state, file_name=STATE_FILE):
    """Write current state to file."""
    with open(file_name, 'w') as fd:
        json.dump(state, fd)


def get_global_init():
    """Read global.init and return config."""
    try:
        with open(GLOBAL_INIT) as fd:
            config = json.load(fd)
            return config
    except FileNotFoundError:
        return {}


def get_destinations(config):
    """Return destination to be pinged."""
    destinations = []
    # first ping conductor ip addresses
    try:
        for conductor in config['init']['conductor'].values():
            conductor_ip = conductor['host']
            destinations.append(conductor_ip)
    except KeyError:
        pass

    # then try a test host - in case of conductor downtime
    destinations.append(TEST_HOST)
    return destinations


def get_node_name(config):
    """Set node name based on global.init config."""
    try:
        node_name = config['init']['id']
    except KeyError:
        node_name = "unknown-node-name"
    return node_name


def safety_net_is_enabled():
    """Return if safety_net service is running."""
    try:
        check_call(['systemctl', 'is-active', '--quiet', 'safety_net'])
        return True
    except CalledProcessError:
        return False


def main():
    """Run Main loop."""
    config = get_global_init()
    node_name = get_node_name(config)
    destinations = get_destinations(config)
    state = read_state()

    # Round seconds to current minute
    this_minute = int(time() / 60) * 60

    # When safety net is enabled: consider current time as successful
    # to avoid immediate reboot after safety_net stop (e.g. 128T upgrades)
    if safety_net_is_enabled():
        state['last_success'] = this_minute
        log_journal('Safety_net is running. Do not perform checks.')
        write_state(state)
        return

    # When any destination can be pinged,
    # write success to state file and break the loop.
    for destination in destinations:
        try:
            check_call(
                PING_COMMAND.split(' ') + [destination],
                stdout=DEVNULL)
            state['state'] = 'success'
            state['last_success'] = this_minute
            log_journal('Ping to', destination, 'was successful.')
            write_state(state)
            return
        except CalledProcessError:
            pass

    # When none can be pinged and state timeout is in state file
    # -> reboot machine
    if state['state'] == 'timeout':
        log_journal('Pinging was unsuccessful and 128T restart did not help.',
                    'Reboot machine.')
        send_mail('{}: Restart 128T on node {}'.format(basename, node_name),
                  'Last successful ping on: {} {}'.format(
                      ctime(state['last_success']), strftime("%z")))
        call(REBOOT_CMD.split(' '))
        return

    # When none can be pinged and <timeout> minutes have been passed
    # -> write timeout to state file, restart 128T, and break the loop
    try:
        if this_minute - state['last_success'] > (TIMEOUT * 60):
            state['state'] = 'timeout'
            log_journal('Pinging was unsuccessful over the last', TIMEOUT,
                        'minutes.', 'Restarting 128T service.')
            send_mail('{}: Reboot node {}'.format(basename, node_name),
                      'Last successful ping on: {} {}'.format(
                            ctime(state['last_success']), strftime("%z")))
            call(RESTART_CMD.split(' '))
            write_state(state)
    except KeyError:
        log_journal('Could not find "last_success" in state file.')


if __name__ == '__main__':
    main()
