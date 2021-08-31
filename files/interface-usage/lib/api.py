import os
import requests
import time

from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


class UnauthorizedException(Exception):
    pass


def extract(data, find_key):
    if type(data) == list:
        # descent to first element in list
        return extract(data[0], find_key)
    if type(data) == dict:
        if find_key in data:
            return data[find_key]
        for key, value in data.items():
            # descent to first element in dictionary
            return extract(value, find_key)


class RestGraphqlApi(object):
    """Representation of REST connection."""

    token = None
    authorized = False

    def __init__(self, host='localhost', verify=False):
        self.host = host
        self.verify = verify
        self.session = requests.Session()

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
        request = self.session.get(
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
        request = self.session.post(
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
        request = self.session.patch(
            url, headers=headers, json=json,
            verify=self.verify)
        return request

    def query(self, query, authorization_required=True):
        """Execute a graphql query."""
        url = 'https://{}/api/v1/graphql'.format(self.host)
        headers = {
            'Content-Type': 'application/json',
        }
        json = {
            'query': query,
        }
        # Login if not yet done
        if authorization_required:
            if not self.authorized:
                self.login()
            if self.token:
                headers['Authorization'] = 'Bearer {}'.format(self.token)

        request = self.session.post(
            url, headers=headers, json=json,
            verify=self.verify)
        return request

    def login(self, user='admin'):
        key_file = 'pdc_ssh_key'
        if not os.path.isfile(key_file):
            key_file = '/home/admin/.ssh/pdc_ssh_key'

        key_content = ''
        with open(key_file) as fd:
            key_content = fd.read()
        json = {
            'username': user,
            'local': key_content
        }
        request = self.post('/login', json, authorization_required=False)
        if request.status_code == 200:
            self.token = request.json()['token']
            self.authorized = True
        else:
            message = request.json()['message']
            raise UnauthorizedException(message)

    def get_routers(self):
        return self.get('/router').json()

    def get_router_name(self):
        self.router_name = self.get_routers()[0]['name']
        return self.router_name

    def get_nodes(self, router_name):
        return self.get('/config/running/authority/router/{}/node'.format(
            router_name)).json()

    def get_node_name(self):
        request = self.get('/router/{}/node'.format(self.router_name))
        self.node_name = request.json()[0]['name']
        return self.node_name

    # def get_device_interfaces(self, router_name, node_name):
    #     request = self.get('/router/{}/node/{}/deviceInterface'.format(
    #         router_name, node_name))
    #     if request.status_code == 200:
    #         return request.json()
    #     else:
    #         return []
    #
    # def get_network_interfaces(self, router_name, node_name, device_name):
    #     request = self.get('/router/{}/node/{}/deviceInterface/{}/networkInterface'.format(
    #         router_name, node_name, device_name))
    #     if request.status_code == 200:
    #         return request.json()
    #     else:
    #         return []
    #
    def get_interfaces(self):
        _query = '{ allRouters { nodes { name nodes { nodes { name deviceInterfaces { nodes { name type } } } } } } }'
        request = self.query(_query)
        if request.status_code == 200:
            return request.json()
        else:
            return []

    def get_interface_usage(self, router, node, interface):
        query = '''{ metrics { interface { %(kpi)s {
                      bytes(router: "%(router)s", node: "%(node)s", port: "%(interface)s") {
                      timeseries(startTime: "now-10") { timestamp value } } } } } }'''
        stats = [int(time.time())]
        for kpi in ('received', 'sent'):
            result = self.query(query % locals())
            # print('result:', result.json())
            try:
                value = int(extract(result.json(), 'value'))
            except (TypeError, IndexError):
                return None
            stats.append(value)
        return tuple(stats)
