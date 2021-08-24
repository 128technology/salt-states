#!/usr/bin/env python3

import argparse
import os
import requests
import sys

from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


class UnauthorizedException(Exception):
    pass


class RestGraphqlApi(object):
    """Representation of REST connection."""

    token = None
    authorized = False

    def __init__(self, host='localhost', verify=False, user='admin', password=None):
        self.host = host
        self.verify = verify
        self.user = user
        self.password = password

    def get(self, location, authorization_required=True):
        """Get data per REST API."""
        url = 'https://{}/api/v1/{}'.format(self.host, location.strip('/'))
        headers = {
            'Content-Type': 'application/json',
        }
        if authorization_required:
            if not self.authorized:
                self.login()
            if self.token:
                headers['Authorization'] = 'Bearer {}'.format(self.token)
        request = requests.get(
            url, headers=headers,
            verify=self.verify)
        return request

    def post(self, location, json, authorization_required=True):
        """Send data per REST API via post."""
        url = 'https://{}/api/v1/{}'.format(self.host, location.strip('/'))
        headers = {
            'Content-Type': 'application/json',
        }
        # Login if not yet done
        if authorization_required:
            if not self.authorized:
                self.login()
            if self.token:
                headers['Authorization'] = 'Bearer {}'.format(self.token)
        request = requests.post(
            url, headers=headers, json=json,
            verify=self.verify)
        return request

    def patch(self, location, json, authorization_required=True):
        """Send data per REST API via patch."""
        url = 'https://{}/api/v1/{}'.format(self.host, location.strip('/'))
        headers = {
            'Content-Type': 'application/json',
        }
        # Login if not yet done
        if authorization_required:
            if not self.authorized:
                self.login()
            if self.token:
                headers['Authorization'] = 'Bearer {}'.format(self.token)
        request = requests.patch(
            url, headers=headers, json=json,
            verify=self.verify)
        return request

    def login(self):
        json = {
            'username': self.user,
        }
        if self.password:
            json['password'] = self.password
        else:
            key_file = 'pdc_ssh_key'
            if not os.path.isfile(key_file):
                key_file = '/home/admin/.ssh/pdc_ssh_key'

            key_content = ''
            with open(key_file) as fd:
                key_content = fd.read()
            json['local'] = key_content
        request = self.post('/login', json, authorization_required=False)
        if request.status_code == 200:
            self.token = request.json()['token']
            self.authorized = True
        else:
            message = request.json()['message']
            raise UnauthorizedException(message)

    def get_routers(self):
        return self.get('/router').json()

    def get_nodes(self, router_name):
        return self.get('/config/running/authority/router/{}/node'.format(
            router_name)).json()

    def has_uncommitted_changes(self):
        """Return whether conductor's candidate config differs from running."""
        request = self.get('/config/version?datastore=candidate')
        if request.status_code != 200:
            fatal('Cannot connect to REST API.')
        return request.json()['isDirty']


def log(*messages):
    """Write messages to log file."""
    print(*messages)

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


def parse_arguments():
    """Get commandline arguments."""
    parser = argparse.ArgumentParser(
        description='Configure selected options of 128T routers')
    parser.add_argument('--router', '-r', help='Router name', required=True)
    parser.add_argument('--commit', '-c', help='Commit config',
                         action='store_true')
    parser.add_argument('--yes', help='Commit unconfirmed', action='store_true')
    parser.add_argument('--asset-id', '-a', help='Change asset id')
    parser.add_argument('--enable-asset-resilency', action='store_true')
    parser.add_argument('--enable-maintenance-mode', action='store_true')
    parser.add_argument('--disable-maintenance-mode', action='store_true')
    # for remote conductor (e.g. testing purposes)
    parser.add_argument('--host', help='Conductor hostname')
    parser.add_argument('--user', help='Conductor username (if not localhost)')
    parser.add_argument('--password', help='Conductor password (if not localhost)')
    return parser.parse_args()


def get_config(api, locations, router_name, node_name):
    config = {}
    for dict_key, tup in locations.items():
        location = tup[0].format(router=router_name, node=node_name)
        key = tup[1]
        config[dict_key] = api.get('/config/running' + location).json()[key]
    return config

def update_config(api, locations, router_name, node_name, changes):
    for dict_key, new_value in changes.items():
        tup = locations[dict_key]
        location = tup[0].format(router=router_name, node=node_name)
        key = tup[1]
        api.patch('/config/candidate' + location, {key: new_value})


def show_changes(router_name, current_config, new_config, commit):
    if current_config == new_config:
        info('Nothing has changed.')
        return {}

    if commit:
        mode = 'committed'
    else:
        mode = 'applied to candidate config'
    print('The following changes for router {} will be {}:'.format(
        router_name, mode))
    changes = {}
    for key, value in current_config.items():
        new_value = new_config[key]
        if new_value != value:
            changes[key] = new_value
            print('{}: {} => {}'.format(key, value, new_value))
    return changes


def main():
    args = parse_arguments()
    params = {}
    if args.host:
        params['host'] = args.host
        if args.user and args.password:
            params['user'] = args.user
            params['password'] = args.password
    api = RestGraphqlApi(**params)

    if api.has_uncommitted_changes():
        fatal('Conductor has uncommitted changes.',
              'Quit here to avoid commit conflicts.')

    router_name = args.router
    routers = [r['name'] for r in api.get_routers()]
    if router_name not in routers:
        fatal('Specified router in unknown on conductor:', router_name)

    nodes = api.get_nodes(router_name)
    num_nodes = len(nodes)
    if num_nodes != 1:
        fatal('This script supports only routers with one node.',
               num_nodes,'found.')
    node_name = nodes[0]['name']
    locations = {
        'maintenance-mode': ('/authority/router/{router}', 'maintenance-mode'),
        'asset-connection-resiliency': ('/authority/router/{router}/system/asset-connection-resiliency', 'enabled'),
        'asset-id': ('/authority/router/{router}/node/{node}', 'asset-id'),
    }

    current_config = get_config(api, locations, router_name, node_name)
    new_config = current_config.copy()

    if args.asset_id:
        new_config['asset-id'] = args.asset_id
    if args.enable_asset_resilency:
        new_config['asset-connection-resiliency'] = 'true'
    if args.enable_maintenance_mode:
        new_config['maintenance-mode'] = True
    if args.disable_maintenance_mode:
        new_config['maintenance-mode'] = False

    changes = show_changes(router_name, current_config, new_config, args.commit)
    if not changes:
        return

    if not args.yes:
        answer = input('Please confirm (y/n): ')
        if answer.lower() not in ('y', 'yes'):
            return

    update_config(api, locations, router_name, node_name, changes)
    if args.commit:
        api.post('/config/commit', {})
        info('Changes from candidate to running config have been committed.')
    else:
        warning('No --commit argument given. Candidate config has been updated, but NOT committed!')


if __name__ == '__main__':
    main()
