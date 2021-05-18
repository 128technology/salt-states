import json
import random
import time
from lib.cmd import run_command
from lib.log import debug, info
name = 'ookla'


def run_speedtest(namespace, server_id=None):
    inner_cmd = '/usr/bin/env speedtest --format=json --accept-license --accept-gdpr'
    if server_id:
        inner_cmd = '{} --server-id {}'.format(inner_cmd, server_id)
    netns = 'ip netns exec {} {}'.format(namespace, inner_cmd)
    result = run_command(netns)
    if result.returncode == 0:
        measurements = json.loads(result.stdout.decode('utf8'))
        return measurements
    else:
        return {}

def get_results(interface, interface_stats, max_delay):
    namespace = 'speed-{}'.format(interface).lower()
    delay = random.randint(0, max_delay)
    info('Delay speedtest execution by {} seconds.'.format(delay))
    time.sleep(delay)
    return run_speedtest(namespace)
