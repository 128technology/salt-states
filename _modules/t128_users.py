import json
import logging
import pathlib
import requests

log = logging.getLogger(__name__)

WEB_SOCKET_PATH = pathlib.Path("/var/run/128technology/web-server.sock")
PRE_128T_4_4_PORT = 31516
POST_128T_4_4_PORT = 31517

GRAPHQL_ENDPOINT = 'http://localhost:{}/api/v1/graphql'
REQUEST_HEADERS = {"Content-Type":"application/json", 
                   "Accept":"application/json"}

_GET_USERS_QUERY = """
query{
  allRouters{
    nodes{
      users{
        nodes{
          name,
          role,
          enabled,
          fullName
        }
      }
    }
  }
}
"""

_CREATE_USER_START = """
mutation{{
  createUser(user:{{name:{name},
"""

_MODIFY_USER_START = """
mutation{{
  modifyUser(user:{{name:{name},
"""

_END_MUTATION = """
                  }
            )
  {
    id
  }
}
"""

_DELETE_USER_TEMPLATE = """
mutation{{
  deleteUser(name:{name}) 
}}
"""

def _get_url():
    port = POST_128T_4_4_PORT if WEB_SOCKET_PATH.exists() else PRE_128T_4_4_PORT
    return GRAPHQL_ENDPOINT.format(port)

def get_users():
    users = {}
    resp = requests.post(_get_url(),
                         headers=REQUEST_HEADERS,
                         json={"query":_GET_USERS_QUERY})
    if not resp.ok:
        log.debug("Received error code {}: {}".format(resp.status_code,resp.json()))
        return False

    try :
        user_list = resp.json()['data']['allRouters']['nodes'][0]['users']['nodes']
    except TypeError:
        log.debug("GraphQL Response: {}".format(resp.json()))
        return False

    for user in user_list:
        username = user['name']
        users[username] = user

    return users

def add_user(name,
             role="user",
             enabled=True,
             fullName=None,
             password=None):

    if role and type(role) is not list:
        role = [role]

    if role is None:
        role = ["user"]

    query = _CREATE_USER_START.format(name=json.dumps(name))
    if role:
        query += '                    role:{role}\n'.format(role=json.dumps(role))
    if enabled is not None:
        query += '                    enabled:{enabled}\n'.format(enabled=json.dumps(enabled))
    if fullName:
        query += '                    fullName:{fullName}\n'.format(fullName=json.dumps(fullName))
    if password:
        query += '                    password:{password}\n'.format(password=json.dumps(password))
    query += _END_MUTATION

    resp = requests.post(_get_url(),
                         headers=REQUEST_HEADERS,
                         json={"query": query})

    if not resp.ok:
        log.debug("Received error code {}: {}".format(resp.status_code,resp.json()))
        return False

    try:
        if str(resp.json()['data']['createUser']['id']) == name:
            return True
        else:
            log.debug("GraphQL Response: {}".format(resp.json()))
            return False
    except (KeyError, TypeError):
        log.debug("GraphQL Response: {}".format(resp.json()))
        return False
    
def modify_user(name,
                role=None,
                enabled=None,
                fullName=None,
                password=None):
    query = _MODIFY_USER_START.format(name=json.dumps(name))
    if role:
        query += '                    role:{role}\n'.format(role=json.dumps(role))
    if enabled is not None:
        query += '                    enabled:{enabled}\n'.format(enabled=json.dumps(enabled))
    if fullName:
        query += '                    fullName:{fullName}\n'.format(fullName=json.dumps(fullName))
    if password:
        query += '                    password:{password}\n'.format(password=json.dumps(password))
    query += _END_MUTATION

    resp = requests.post(_get_url(),
                         headers=REQUEST_HEADERS,
                         json={"query": query})

    if not resp.ok:
        log.debug("Received error code {}: {}".format(resp.status_code,resp.json()))
        return False

    try:
        if str(resp.json()['data']['modifyUser']['id']) == name:
            return True
        else:
            log.debug("GraphQL Response: {}".format(resp.json()))
            return False
    except (KeyError, TypeError):
        log.debug("GraphQL Response: {}".format(resp.json()))
        return False

def delete_user(name):
    resp = requests.post(_get_url(),
                         headers=REQUEST_HEADERS,
                         json={"query":_DELETE_USER_TEMPLATE.format(name=json.dumps(name))})
    if not resp.ok:
        log.debug("Received error code {}: {}".format(resp.status_code,resp.json()))
        return False

    try:
        if resp.json()['data']['deleteUser']:
            return True
        else:
            return False
    except KeyError:
        log.debug("GraphQL Response: {}".format(resp.json()))
        return False
