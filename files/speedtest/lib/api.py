import os
import requests

from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


class UnauthorizedException(Exception):
    pass


class RestGraphqlApi(object):
    """Representation of REST connection."""

    token = None
    authorized = False

    def __init__(self, host='localhost', verify=False):
        self.host = host
        self.verify = verify

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

        # import logging
        # try:
        #     import http.client as http_client
        # except ImportError:
        #     # Python 2
        #     import httplib as http_client
        # http_client.HTTPConnection.debuglevel = 1
        # logging.basicConfig()
        # logging.getLogger().setLevel(logging.DEBUG)
        # requests_log = logging.getLogger("requests.packages.urllib3")
        # requests_log.setLevel(logging.DEBUG)
        # requests_log.propagate = True

        request = requests.post(
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
