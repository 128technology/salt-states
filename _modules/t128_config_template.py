#!/usr/bin/python

import os
import jinja2
import jinja2.exceptions
import logging
import sys
import t128_netconf_utilities

try:
  from lxml import etree
  from ncclient import manager
  if sys.version_info < (3, 6):
    from ote_utils.utils import Config
  else:
    from ote_utils.netconfutils.netconfconverter import NetconfConverter
  IMPORT_SUCCESS = True
except ImportError:
  IMPORT_SUCCESS = False


T128_NS = {'t128':'http://128technology.com/t128'}
AUTHORITY_NS = {'authority-config':'http://128technology.com/t128/config/authority-config'}
SYSTEM_NS = {'system-config':'http://128technology.com/t128/config/system-config'}
INTERFACE_NS = {'interface-config':'http://128technology.com/t128/config/interface-config'}
SERVICE_NS = {'service-config':'http://128technology.com/t128/config/service-config'}
LOG_DIRECTORY = '/var/log/128technology'

if not os.path.exists(LOG_DIRECTORY):
    os.makedirs(LOG_DIRECTORY)
logger = logging.getLogger(__name__)
handler = logging.FileHandler('{0}/{1}.log'.format(LOG_DIRECTORY,'t128_netconf'))
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
handler.setFormatter(formatter)
logger.addHandler(handler)

def __virtual__():
  if IMPORT_SUCCESS:
    return True
  else:
    return (False, "There was an error importing a required package")

class Returner(object):

    def __init__(self, returner, name, changes, result, comment):
        if returner == "saltstack":
            self.ret = {'name': name, 'changes': changes, 'result': result, 'comment': comment}

    def getReturn(self):
        return self.ret

def _get_current_config_text(host='127.0.0.1', port='830', username='admin', key_filename='/etc/128technology/ssh/pdc_ssh_key'):
  with manager.connect(host=host, port=port, username=username, key_filename=key_filename, allow_agent=True, look_for_keys=False, hostkey_verify=False) as m:
    c = m.get_config(source='running').data
  return c.find('t128:config', namespaces=T128_NS)

def _create_add_config(template, name):
  context = {}
  context['name'] = name
  try:
    context['router'] = __pillar__[name]
  except KeyError:
    return ''
  try:
    JINJA = jinja2.Environment(
      loader=jinja2.FileSystemLoader('/')
    )
    template_location = __salt__['cp.cache_file']('salt://config_templates/{0}.jinja'.format(template))
    if template_location:
      template = JINJA.get_template(template_location)
    else:
      logger.error('Could not find template file {0}.jinja'.format(template))
      return ''
  except jinja2.exceptions.TemplateNotFound:
    logger.error('Could not load template {0}.jinja'.format(template))
    return ''
  return template.render(context)

def _create_delete_config(delete_router_name):
  config = _get_current_config_text()
  authority = config.find('authority-config:authority', namespaces=AUTHORITY_NS)
  routers = authority.findall('authority-config:router', namespaces=AUTHORITY_NS)
  delete_string = ''
  for router in routers:
    router_name = router.find('authority-config:name', namespaces=AUTHORITY_NS).text
    if router_name == delete_router_name:
      delete_string+="        delete router          {0}\n".format(router_name) + \
                     "            name  {0}\n".format(router_name) + \
                     "        exit\n"
    else:
      router_config_string = "        router    {0}\n            name  {0}\n".format(router_name)
      peers = router.findall('authority-config:peer', namespaces=AUTHORITY_NS)
      service_routes = router.findall('service-config:service-route', namespaces=SERVICE_NS)
      peer_delete_string = ''
      peer_matches = []
      service_route_delete_string = ''
      for peer in peers:
        peer_router_name = peer.find('authority-config:router-name', namespaces=AUTHORITY_NS).text
        peer_name = peer.find('authority-config:name', namespaces=AUTHORITY_NS).text
        if peer_router_name == delete_router_name:
          peer_matches.append(peer_name)
          peer_delete_string+="            delete peer                  {0}\n".format(peer_name) + \
                              "                name                   {0}\n".format(peer_name) + \
                              "            exit\n"
          for service_route in service_routes:
            service_route_peer = None
            service_route_peer_obj = service_route.find('service-config:peer', namespaces=SERVICE_NS)
            if service_route_peer_obj is not None:
              service_route_peer = service_route_peer_obj.text
            service_route_name = service_route.find('service-config:name', namespaces=SERVICE_NS).text
            if service_route_peer and (service_route_peer == peer_name):
              service_route_delete_string+="            delete service-route         {0}\n".format(service_route_name) + \
                                           "                name                     {0}\n".format(service_route_name) + \
                                           "            exit\n"
      if peer_delete_string != '':
        delete_string+=router_config_string+peer_delete_string
        if service_route_delete_string != '':
          delete_string+=service_route_delete_string
        nodes = router.findall('system-config:node', namespaces=SYSTEM_NS)
        node_delete_string = ''
        for node in nodes:
          node_name = node.find('system-config:name', namespaces=SYSTEM_NS).text
          node_config_string = "            node                  {0}\n".format(node_name) + \
                               "                name              {0}\n".format(node_name)
          device_interfaces = node.findall('system-config:device-interface', namespaces=SYSTEM_NS)
          di_delete_string = ''
          for device_interface in device_interfaces:
            device_id = device_interface.find('system-config:id', namespaces=SYSTEM_NS).text
            di_config_string = "                device-interface  {0}\n".format(device_id) + \
                               "                    id            {0}\n".format(device_id)
            network_interfaces = device_interface.findall('interface-config:network-interface', namespaces=INTERFACE_NS)
            ni_delete_string = ''
            for network_interface in network_interfaces:
              ni_name = network_interface.find('interface-config:name', namespaces=INTERFACE_NS).text
              ni_config_string = "                    network-interface    {0}\n".format(ni_name) + \
                                 "                        name             {0}\n".format(ni_name)
              adjacencies = network_interface.findall('interface-config:adjacency', namespaces=INTERFACE_NS)
              adjacency_delete_string = ""
              for adjacency in adjacencies:
                adj_peer_name = adjacency.find('interface-config:peer', namespaces=INTERFACE_NS).text
                adj_peer_ip = adjacency.find('interface-config:ip-address', namespaces=INTERFACE_NS).text
                if adj_peer_name in peer_matches:
                  adjacency_delete_string+="                        delete adjacency     {0}\n".format(adj_peer_ip) + \
                                           "                           ip-address          {0}\n".format(adj_peer_ip) + \
                                           "                        exit\n"
              if adjacency_delete_string != "":
                ni_delete_string+= ni_config_string + adjacency_delete_string + '                    exit\n'
            if ni_delete_string != "":
              di_delete_string+= di_config_string + ni_delete_string + '                exit\n'
          if di_delete_string != "":
            node_delete_string+= node_config_string + di_delete_string + '            exit\n'
        if node_delete_string != '':
          delete_string+= node_delete_string
        delete_string+="        exit\n"
  if delete_string:
    delete_string = "config\n    authority\n" + delete_string + "    exit\nexit\n"
  return delete_string

def add_router(template_name, router_name, validationType='distributed'):
  logger.info("Adding config for router {0} using template {1}".format(router_name, template_name))
  add_config = _create_add_config(template_name, router_name)
  if add_config:
    logger.debug("Rendered add router config: {0}".format(add_config))
    if sys.version_info < (3,6):
      cc = Config.Config()
      cc.load_t128_config_model('/var/model/consolidatedT128Model.xml')
      add_config_xml = cc.convert_config_to_netconf_xml(add_config.split('\n'))
    else:
      cc = NetconfConverter()
      cc.load_config_model('/var/model/consolidatedT128Model.xml')
      add_config_xml = cc.convert_config_to_netconf_xml(add_config.split('\n'), 'config')
    ch = t128_netconf_utilities.t128ConfigHelper()
    return ch.commit_config_xml(add_config_xml, validationType=validationType)
  else:
    ret = Returner(returner='saltstack', name="add_router", changes={}, result=False, comment="Could not find a router or template by the given name")
    return ret.getReturn()

def delete_router(delete_router_name, validationType='distributed'):
  logger.info("Deleting router {0}".format(delete_router_name))
  delete_config = _create_delete_config(delete_router_name)
  if delete_config:
    logger.debug("Rendered delete router config: {0}".format(delete_config))
    cc = Config.Config()
    cc.load_t128_config_model('/var/model/consolidatedT128Model.xml')
    delete_config_xml = cc.convert_config_to_netconf_xml(delete_config.split('\n'))
    ch = t128_netconf_utilities.t128ConfigHelper()
    return ch.commit_config_xml(delete_config_xml, validationType=validationType)
  else:
    ret = Returner(returner='saltstack', name="delete_router", changes={}, result=False, comment="Could not find a router by the given name")
