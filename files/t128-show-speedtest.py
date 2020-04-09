#!/usr/bin/env python

from __future__ import print_function
import argparse
from datetime import datetime
import json
import sys
import time

import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import salt.client

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


class RestApi:
    """Representation of REST connection."""

    def __init__(self, config, conductor):
        """Constructor - loading credentials."""
        args = parse_arguments()
        self.config = config
        self.conductor = conductor
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer {}'.format(self.config['api_key']),
        }
        self.base_url = 'https://{}/api/v1{}'

    def get(self, location):
        """Get data per REST API."""
        url = self.base_url.format(self.conductor, location)
        response = requests.get(url, headers=self.headers, verify=False)
        return response.json()

    def post(self, location, data):
        """Send data per REST API via post."""
        url = self.base_url.format(self.conductor, location)
        response = requests.post(url, headers=self.headers, verify=False,
                                 data=data)
        return response

    def patch(self, location, data):
        """Send data per REST API via patch."""
        url = self.base_url.format(self.conductor, location)
        response = requests.patch(url, headers=self.headers, verify=False,
                                  data=data)
        return response

    def get_routers(self):
        return self.get('/router')

    def get_nodes(self, router):
        return self.get('/config/running/authority/router/{}/node'.format(
            router))

    def get_interfaces(self, router, node):
        location = '/config/running/authority/router/{}/node/{}/device-interface'.format(
            router, node)
        return [interface['name'] for interface in self.get(location)]

    def set_description(self, router, description):
        if description:
            location = '/config/candidate/authority/router/{}'.format(router)
            return self.patch(location, '{{ "description": "{}"}}'.format(
                description))

    def commit(self):
        return self.post('/config/commit', '{ "distributed": true }')


class NoResultException(Exception):
    pass


def parse_arguments():
    """Get commandline arguments."""
    parser = argparse.ArgumentParser(
        description='Runs speedtest and updates routers description.')
    parser.add_argument('--config', '-c', help='config file', required=True)
    parser.add_argument('--conductor', help='conductor', default='localhost')
    args = parser.parse_args()
    return args


def log(*messages):
    """Write messages to log file."""
    with open('/var/log/t128-show-speedtest.log', 'a') as fd:
        fd.write('{:%Y-%m-%d %H:%M:%S UTC} | {}\n'.format(
            datetime.utcnow(), ' '.join(messages)))


def info(*messages):
    log('INFO:', *messages)


def warn(*messages):
    log('WARNING:', *messages)


def salt_run(asset_id, cmd):
    """Run a command on salt minion."""
    local = salt.client.LocalClient('/etc/128technology/salt/master')
    result = local.cmd(asset_id, 'cmd.run', [cmd])[asset_id]
    if 'command not found' in result:
        warn('Error on node:', asset_id, result)
    return result


def salt_run_async(asset_id, cmd):
    """Run a command on salt minion."""
    local = salt.client.LocalClient('/etc/128technology/salt/master')
    local.cmd_async(asset_id, 'cmd.run', [cmd])


def retrieve_result(asset_id, suffix):
    results = {}
    cmd = 'cat /tmp/speedtest_{}.json'.format(suffix)
    try:
        result = salt_run(asset_id, cmd)
        results_dict = json.loads(result)
        download = int(results_dict['download']['bandwidth']*8/1000000)
        upload = int(results_dict['upload']['bandwidth']*8/1000000)
        return (download, upload)
    except (TypeError, KeyError, ValueError):
        return None


def run_speedtest(asset_id, suffix, server=None):
    inner_cmd = 'speedtest --format=json --accept-license --accept-gdpr'
    if server:
        inner_cmd = '{} --server-id {}'.format(inner_cmd, server)
        suffix = '{}_{}'.format(suffix, server)
    cmd = 'screen -dm bash -c "HOME=/root {} > /tmp/speedtest_{}.json"'.format(
        inner_cmd, suffix)
    try:
        salt_run_async(asset_id, cmd)
        # wait for the speedtest to be finished
        time.sleep(40)
    except (TypeError, KeyError, ValueError):
        warn('No speedtest result for:', router_name)
        raise NoResultException


def get_suffix(run, server_id=None):
    """Generate suffix on run timestamp and server_id."""
    suffix = run
    if server_id:
        suffix = '{}_{}'.format(suffix, server)
    return suffix


def main():
    args = parse_arguments()
    config = json.load(open(args.config))
    api = RestApi(config, args.conductor)
    prefix = config['prefix']
    sys.stdout.close()

    run = int(time.time())
    for router in api.get_routers():
        router_name = router['name']

        # How to handle existing description field? Do not overwrite it!
        description = router['description']
        if description and not description.startswith(prefix):
            warn('Not overwriting description for router {}'.format(
                    router['name']))
            continue

        nodes = api.get_nodes(router['name'])
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

        # Lookup interfaces:
        # * use default for known default interfaces
        # * use extra interfaces with specific server (see config)
        suffixes = []
        stats = []
        interfaces = api.get_interfaces(router_name, node_name)
        try:
            # seek for default interface
            for interface in config['default_interfaces']:
                if interface in interfaces:
                    suffix = get_suffix(run)
                    run_speedtest(asset_id, suffix)
                    suffixes.append((suffix, interface))
                    break

            # seek for extra_interfaces
            extra_interfaces = config['extra_interfaces']
            for interface in extra_interfaces:
                if interface in interfaces:
                    server = extra_interfaces[interface]
                    suffix = get_suffix(run, server)
                    run_speedtest(asset_id, suffix, server)
                    suffixes.append((suffix, interface))

            # retrieve result in json format
            for suffix, interface in suffixes:
                result = retrieve_result(asset_id, suffix)
                if not result:
                    warn('No speedtest result for:', router_name)
                    raise NoResultException
                download, upload = result
                stats.append('{}: {} Mbps down | {} Mbps up'.format(
                    interface, download, upload))
            if not stats:
                continue
            info('{}: {}'.format(router_name, ' / '.join(stats)))
            description = '{}: {}'.format(prefix, ' / '.join(stats))
            api.set_description(router_name, description)
            api.commit()

        except NoResultException:
            pass

if __name__ == '__main__':
    main()
