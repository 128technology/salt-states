#!/usr/bin/env python3

import argparse
import json
import time

from lib import salt
from lib.log import *
from lib import log
from lib.api import RestGraphqlApi


def parse_arguments():
    """Get commandline arguments."""
    parser = argparse.ArgumentParser(
        description='Collect speedtest measurements and update conductor.')
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--host', default='localhost')
    parser.add_argument('--log-file', default=log.LOGFILE)
    parser.add_argument('--max-age', default=12, type=int, help='maximum age of speedtest results (in hours)')
    parser.add_argument('--results-file', default='/var/lib/128technology/t128-speedtest-results.json')
    parser.add_argument('--router', action='append', default=[])
    args = parser.parse_args()
    return args


def has_uncommitted_changes(api):
    """Return whether conductor's candidate config differs from running."""
    request = api.get('/config/version?datastore=candidate')
    if request.status_code != 200:
        fatal('Cannot connect to REST API.')
    return request.json()['isDirty']


def update_descriptions(api, descriptions):
    for router, description in descriptions:
        location = '/config/candidate/authority/router/{}'.format(router)
        info('Updating description for router {}: {}'.format(router, description))
        api.patch(location, {'description': description})
    api.post('/config/commit', {})


def process_routers(api, results_file, routers, max_age, prefix='(Speedtest:', suffix=')'):
    """Iterate over routers and update the description field accordingly."""
    descriptions = []
    for router in api.get_routers():
        router_name = router['name']
        debug('Process router:', router_name)

        # if a subset of routers is specified, check if current is listed
        if routers and router_name not in routers:
            continue

        description = router['description']
        nodes = api.get_nodes(router_name)
        if len(nodes) != 1:
            # How to handle more than one router node? Log a warning!
            warn('The script supports only routers with one node:',
                 router_name)
            continue

        node = nodes[0]
        node_name = node['name']
        if node['role'] == 'conductor':
            # ignore conductor nodes
            continue

        try:
            asset_id = node['asset-id']
        except KeyError:
            # ignore nodes without asset_id
            continue
        results_dict = salt.retrieve_result(asset_id, results_file)
        if not results_dict:
            continue
        debug('results_dict for asset {}: {}'.format(asset_id, results_dict))

        interface_strings = []
        for module, module_results in results_dict.items():
            for interface, interface_results in module_results.items():
                if not interface_results.get('download') or \
                   not interface_results.get('upload'):
                    continue
                if interface_results.get('ts') + max_age * 3600 < time.time():
                    info('Ignoring too old results for router:', router_name)
                    continue
                download = int(interface_results['download']['bandwidth']*8/1000000)
                upload = int(interface_results['upload']['bandwidth']*8/1000000)
                interface_strings.append('{}: {} Mbps down, {} Mbps up'.format(
                    interface, download, upload))

        if interface_strings:
            interface_description = '{} {}{}'.format(
                prefix, ' | '.join(interface_strings), suffix)
            if description:
                # TODO: regex to replace substring
                description = '{} {}'.format(
                    description.split(prefix)[0].strip(' '),
                    interface_description)
            else:
                description = interface_description
            descriptions.append((
                router_name,
                description,
            ))
    debug('Descriptions: {}'.format(descriptions))
    update_descriptions(api, descriptions)


def main():
    args = parse_arguments()
    log.DEBUG = args.debug
    log.LOGFILE = args.log_file
    api = RestGraphqlApi(args.host)

    if has_uncommitted_changes(api):
        fatal('Conductor has uncommitted changes.',
              'Quit here to avoid commit conflicts.')

    process_routers(api, args.results_file, args.router, args.max_age)


if __name__ == '__main__':
    main()
