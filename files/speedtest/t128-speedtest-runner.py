#!/usr/bin/env python3

import argparse
import json
import time

from lib.log import *
from lib import log
from lib.api import RestGraphqlApi
import plugins


def parse_arguments():
    """Get commandline arguments."""
    parser = argparse.ArgumentParser(
        description='Run speedtest and write results to json file.')
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--host', default='localhost')
    parser.add_argument('--log-file', default=log.LOGFILE)
    parser.add_argument('--max-delay', type=int, default=0)
    parser.add_argument('--results-file', default='/var/lib/128technology/t128-speedtest-results.json')
    parser.add_argument('--test', action='append', default=[])
    args = parser.parse_args()
    return args


def get_interface_stats(host):
    stats = {}
    api = RestGraphqlApi(host=host)
    query = '{ allNodes { nodes { deviceInterfaces { nodes { name type state { operationalStatus } } } } } }'
    try:
        interfaces = api.query(query).json()['data']['allNodes']['nodes'][0]['deviceInterfaces']['nodes']
        for interface in interfaces:
            # ignore host interfaces
            if interface['type'] == 'host':
                continue
            stats[interface['name']] = {
                'type': interface['type'],
                'up': interface['state']['operationalStatus'] == 'OPER_UP',
            }
    except:
        fatal('Could not retrieve interfaces status')
    return stats


def write_results(filename, results):
    with open(filename, 'w') as fd:
        json.dump(results, fd)


def main():
    args = parse_arguments()
    log.DEBUG = args.debug
    log.LOGFILE = args.log_file
    results = {}
    stats = get_interface_stats(args.host)
    plugins.load_plugins()
    # iterate over plugins and run get_results for each plugin
    # which is configured and where assigned interfaces are UP
    for plugin in plugins.plugins:
        test_interfaces = [
            x.split(':')[1] for x in args.test if x.startswith(plugin.name)
        ]
        for interface in test_interfaces:
            if interface not in stats:
                debug('Interface', interface, 'is unknown on this router')
                continue
            if not stats[interface]['up']:
                debug('Interface', interface, 'is down - skipping')
                continue
            _interface = interface.replace('local-wan', 'wan')
            result = plugin.get_results(_interface, stats, args.max_delay)
            result['ts'] = int(time.time())
            if plugin.name not in results:
                results[plugin.name] = {}
            results[plugin.name][interface] = result
    write_results(args.results_file, results)


if __name__ == '__main__':
    main()
