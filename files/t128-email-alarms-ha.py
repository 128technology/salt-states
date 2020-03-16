#!/usr/bin/env python

from __future__ import print_function
import argparse
import json
import os
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import smtplib
from subprocess import check_call, check_output, CalledProcessError
import sys
import threading
import time

from jinja2 import Template

# Python 2 backwards compatibility
try:
    from subprocess import DEVNULL  # python3
except ImportError:
    # python2
    import os
    DEVNULL = open(os.devnull, 'wb')

try:
    FileNotFoundError  # python3
except NameError:
    FileNotFoundError = IOError

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
DEBUG = False
TESTING = False
DRY_RUN = False
config = None
mail_interval = 60
template = None
alarms = []
cleaned_duplicates = 0


def parse_arguments():
    """Get commandline arguments."""
    parser = argparse.ArgumentParser(
        description='Monitor 128T alarms and send them via email.')
    parser.add_argument('--config-file', '-c', help='config filename',
                        default='config.json')
    parser.add_argument('--debug', help='enable debug messages',
                        action='store_true')
    parser.add_argument('--dry-run', help='do not send mails',
                        action='store_true')
    parser.add_argument('--testing', help='enable testing mode',
                        action='store_true')
    return parser.parse_args()


def read_json(filename):
    """Read json file."""
    with open(filename) as fd:
        return json.load(fd)


def log(*messages):
    """Log a message."""
    print(*messages)


def debug(*messages):
    """Log debug messages."""
    if DEBUG:
        log('DEBUG:', *messages)


def fatal(*messages):
    """Log fatal message and exit."""
    log('FATAL:', *messages)
    sys.exit(1)


def info(*messages):
    """Log info message."""
    log('INFO:', *messages)


def testing(*messages):
    """Log debug messages."""
    if TESTING:
        log('TESTING:', *messages)


def get_host_ips():
    """Return a list of IP addresses of the host that runs the script."""
    ips = check_output(['hostname', '--all-ip-addresses']).decode('utf8')
    return ips.split()


def ping_node(address):
    """Ping a node."""
    cmd = 'ping -c 1 -w 1 -q'.split(' ')
    cmd.append(address)
    debug('Ping result:', check_call(cmd, stdout=DEVNULL))


def node_is_active():
    """Return true on active node."""
    # lexically sort node names:
    # * return True if we are the first one
    # * else return True if the other peer is unreachable
    try:
        global_init = read_json('/etc/128technology/global.init')
    except FileNotFoundError:
        return True

    control = global_init['init']['control']
    if control:
        # Running on a router
        fatal('This script is designed to run on a conductor. Exiting.')

    host_ips = get_host_ips()
    conductors = global_init['init']['conductor']
    if len(conductors) == 1:
        # Running on non-HA conductor
        return True

    if len(conductors) != 2:
        fatal('Something went wrong. '
              'Number of conductors in global.init should be 2! Exiting.')

    ip_addresses = [c[1]['host'] for c in sorted(conductors.items())]
    host_ips = get_host_ips()
    if ip_addresses[0] in host_ips:
        debug('we are the primary HA node')
        return True
    if ip_addresses[1] in host_ips:
        # we are the secondary HA node
        try:
            ping_node(ip_addresses[0])
            debug('We are the secondary HA node and the primary is up.')
            return False
        except CalledProcessError:
            debug('the primary HA node is down - taking over')
            return True

    fatal('Something went wrong. '
          'Conductor IPs do not match any local IP address. Exiting.')
    sys.exit(1)


def get_template():
    """Initialize template."""
    try:
        template_name = config['template']
        template_path = template_name
        if not os.path.isabs(template_name):
            template_path = os.path.join(sys.path[0], template_name)
        with open(template_path, 'r') as fd:
            template = Template(fd.read())
        return template
    except FileNotFoundError:
        fatal('Template file "{}" could not be found.'.format(template_name))


def create_email_body(mail_from, mail_recipients, alarm):
    """Create email body using template file and data."""
    return template.render(
        alarm=alarm,
        mail_from=mail_from,
        mail_recipients=mail_recipients,
    )


def send_mail(mail_from, mail_recipients, body):
    """Send a mail via smtp."""
    mail_host = config.get('mail_host', 'localhost')
    mail_port = config.get('mail_port', '25')
    mail_tls = config.get('mail_tls', False)
    mail_user = config.get('mail_user')
    mail_pass = config.get('mail_pass')
    if mail_tls:
        server = smtplib.SMTP_SSL(mail_host, mail_port)
    else:
        server = smtplib.SMTP(mail_host, mail_port)
    # TODO implement SMTP AUTH
    if DEBUG:
        server.set_debuglevel(1)
    server.sendmail(mail_from, mail_recipients, body)
    server.quit()


def write_alarms(alarms):
    """Write alarms to json file."""
    processed_alarms = alarms
    try:
        with open('/tmp/processed_alarms.json', 'r') as fd:
            processed_alarms = json.load(fd)
            processed_alarms.extend(alarms)
    except FileNotFoundError:
        pass
    with open('/tmp/processed_alarms.json', 'w') as fd:
            json.dump(processed_alarms, fd)


def replace_messages(alarms):
    """Replace messages in alarms."""
    for alarm in alarms:
        for old, new in config.get('replace_rules', []):
            orig = alarm['message']
            changed = orig.replace(old, new)
            if orig != changed:
                debug('Message replaced:', orig, '=>', changed)
                alarm['message'] = changed


def get_hash(alarm):
    """Calculate hash of an alarm."""
    if config.get('filter_duplicate_alarms', False):
        # build the hash over almost the full alarm
        hash_keys = [
            'category', 'message', 'process', 'router', 'severity']
        return '|'.join([v for k, v in alarm.items() if k in hash_keys])
    else:
        # only use the id
        return alarm['id']


def filter_duplicate_alarms(alarms):
    """Filter alarms if already seen in interval."""
    global cleaned_duplicates
    seen_hashes = []
    seen_add_ids = []
    distinct_alarms = []
    testing('all alarms:', len(alarms))
    for alarm in alarms:
        subtype = alarm['subtype']
        hash = get_hash(alarm)
        if (hash, subtype) in seen_hashes:
            debug('found duplicate:', hash, subtype)
            cleaned_duplicates += 1
            continue
        seen_hashes.append((hash, subtype))
        distinct_alarms.append(alarm)
    return distinct_alarms


def filter_cleared_alarms(alarms):
    """Filter alarms if already cleared in interval."""
    seen_alarms = {}
    for alarm in alarms:
        hash = get_hash(alarm)
        if alarm['subtype'] == 'ADD':
            # we got an add alarm so push it
            seen_alarms[hash] = alarm
        elif alarm['subtype'] == 'CLEAR':
            if hash in seen_alarms and seen_alarms[hash]['subtype'] == 'ADD':
                debug('Popping alarm because clear came within interval.')
                del(seen_alarms[hash])
            else:
                debug('We got a clear that does not match an existing alarm.')
                seen_alarms[hash] = alarm
    testing('added + cleared alarms:', len(alarms),
            'after cleaning add/clear:', len(seen_alarms))
    return list(seen_alarms.values())


def handle_alarms(queue_lock):
    """Consume an alarm."""
    global alarms

    if TESTING:
        time.sleep(1)

    if not alarms:
        # nothing to do during this interval
        return

    # only handling alarms if we are the active node
    if not node_is_active():
        debug('Node is not active. Sleeping until next interval.')
        with queue_lock:
            alarms = []
        return

    # send a mail to configured recipients dependent on the router
    with queue_lock:
        debug('{} alarms in the queue'.format(len(alarms)))
        replace_messages(alarms)
        if config.get('filter_duplicate_alarms', False):
            alarms = filter_duplicate_alarms(alarms)
        if config.get('not_send_cleared_alarms', False):
            alarms = filter_cleared_alarms(alarms)
        for alarm in alarms:
            # lookup recipients
            mail_from = config['mail_from']
            all_recipients = config['mail_recipients']
            mail_recipients = all_recipients['default']
            router = alarm['router']
            if router in all_recipients:
                mail_recipients = all_recipients[router]
            if type(mail_recipients) != list:
                mail_recipients = [mail_recipients]
            mail_recipients_str = ', '.join(mail_recipients)
            email_body = create_email_body(
                mail_from, mail_recipients_str, alarm)
            debug('alarm:', email_body, '\nrecipients:', mail_recipients_str)
            if DRY_RUN:
                # do not send mails
                continue
            info('Sending mail to {} for alarm id {}'.format(
                mail_recipients_str, alarm['id']))
            if not TESTING:
                send_mail(mail_from, mail_recipients, email_body)
        write_alarms(alarms)
        testing('remaining alarms:', len(alarms))
        alarms = []
        testing('cleaned_duplicates:', cleaned_duplicates)


def handle_alarms_thread(queue_lock):
    """Threaded alarm consumer."""
    while True:
        handle_alarms(queue_lock)
        time.sleep(mail_interval)


def receive_alarms(queue_lock):
    """Connect to stream API and receive alarms."""
    global alarms
    url = 'https://{}/api/v1/events?token={}'.format(
        config['api_host'], config['api_key'])
    i = 0
    while True:
        if TESTING and i > 0:
            break
        i = 1
        try:
            if TESTING:
                iterator = open('alarms-stream.txt').readlines()
            else:
                r = requests.get(url, stream=True, verify=False)
                iterator = r.iter_lines()
            for line in iterator:
                if type(line) is bytes:
                    line = line.decode('utf-8')
                if not line.startswith('data: '):
                    continue

                event = json.loads(line.strip('data: '))
                if event['type'] != 'alarm':
                    # unsupported
                    continue

                alarm = event['alarm']
                alarm['subtype'] = event['subtype']

                subject_match = False
                for subject in config.get('ignore_subjects', []):
                    if subject in alarm['message']:
                        subject_match = True
                if subject_match:
                    debug('ignore alarm:', alarm['message'])
                    continue

                if alarm['shelvedStatus'] == 'NOTSHELVED':
                    with queue_lock:
                        # queue an alarm
                        debug('receiver: {} alarms in the queue'.format(
                            len(alarms)))
                        alarm['ts'] = int(time.time())
                        alarms.append(alarm)
                    if mail_interval == 0:
                        # synchronous processing
                        debug('mail_interval is 0, process immediately')
                        handle_alarms(queue_lock)
        except:
            # catch all exceptions for now and re-conncect
            continue


def main():
    global DEBUG
    global TESTING
    global DRY_RUN
    global config
    global mail_interval
    global template
    args = parse_arguments()
    DEBUG = args.debug
    TESTING = args.testing
    DRY_RUN = args.dry_run
    config = read_json(args.config_file)
    mail_interval = config.get('mail_interval', 60)
    template = get_template()

    # setup threads
    queue_lock = threading.Lock()
    threads = []
    receiver = threading.Thread(target=receive_alarms, args=(queue_lock,))
    receiver.start()
    threads.append(receiver)

    if mail_interval > 0:
        if TESTING:
            consumer = threading.Thread(
                target=handle_alarms, args=(queue_lock,))
        else:
            consumer = threading.Thread(
                target=handle_alarms_thread, args=(queue_lock,))
        consumer.start()
        threads.append(consumer)

    # wait for threads to finish
    for thread in threads:
        thread.join()


if __name__ == '__main__':
    main()
