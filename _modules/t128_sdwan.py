#!/usr/bin/python

import os
import jinja2
import jinja2.exceptions
import logging

try:
  from lxml import etree
  from ncclient import manager
  from ote_utils.utils import Config
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
handler = logging.FileHandler('{0}/{1}.log'.format(LOG_DIRECTORY,'t128_sdwan'))
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
    template_location = __salt__['cp.cache_file']('salt://templates/{0}.jinja'.format(template))
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

def _get_authority_map():
  config = _get_current_config_text()
  authority_map = {}
  authority = config.find('authority-config:authority', namespaces=AUTHORITY_NS)
  routers = authority.findall('authority-config:router', namespaces=AUTHORITY_NS)
  for router in routers:
    router_map = {}
    router_name = router.find('authority-config:name', namespaces=AUTHORITY_NS).text
    nodes = router.findall('system-config:node', namespaces=SYSTEM_NS)
    for node in nodes:
      node_map = {}
      node_name = node.find('system-config:name', namespaces=SYSTEM_NS).text
      device_interfaces = node.findall('system-config:device-interface', namespaces=SYSTEM_NS)
      for device_interface in device_interfaces:
        di_map = {}
        device_id = device_interface.find('system-config:id', namespaces=SYSTEM_NS).text
        network_interfaces = device_interface.findall('interface-config:network-interface', namespaces=INTERFACE_NS)
        for network_interface in network_interfaces:
          ni_map = {}
          ni_name = network_interface.find('interface-config:name', namespaces=INTERFACE_NS).text
          ni_sec_obj = network_interface.find('interface-config:inter-router-security', namespaces=INTERFACE_NS)
          if ni_sec_obj is not None:
            ni_map['inter-router-security'] = ni_sec_obj.text
          adjacencies = network_interface.findall('interface-config:adjacency', namespaces=INTERFACE_NS)
          adjacency_map = {}
          for adjacency in adjacencies:
            adj_peer_name_obj = adjacency.find('interface-config:peer', namespaces=INTERFACE_NS)
            adj_peer_ip_obj = adjacency.find('interface-config:ip-address', namespaces=INTERFACE_NS)
            if adj_peer_name_obj and adj_peer_ip_obj:
              adjacency_map[adj_peer_ip.text] = adj_peer_name.text
          ni_map['adjacencies'] = adjacency_map
          ni_neighborhoods = {}
          neighborhoods = network_interface.findall('interface-config:neighborhood', namespaces=INTERFACE_NS)
          for neighborhood in neighborhoods:
            neighborhood_map = {}
            neighborhood_name = neighborhood.find('interface-config:name', namespaces=INTERFACE_NS).text
            neighborhood_topology = None
            neighborhood_topology_obj = neighborhood.find('interface-config:topology', namespaces=INTERFACE_NS)
            if neighborhood_topology_obj is not None:
              neighborhood_topology = neighborhood_topology_obj.text
            neighborhood_ext_nat = None
            neighborhood_ext_nat_obj = neighborhood.find('interface-config:external-nat-address', namespaces=INTERFACE_NS)
            if neighborhood_ext_nat_obj is not None:
              neighborhood_ext_nat = neighborhood_ext_nat_obj.text
            neighborhood_qp = None
            neighborhood_qp_obj = neighborhood.find('interface-config:qp-value', namespaces=INTERFACE_NS)
            if neighborhood_qp_obj is not None:
              neighborhood_qp = neighborhood_qp_obj.text
            neighborhood_bfd = None
            neighborhood_bfd_obj = neighborhood.find('interface-config:bfd', namespaces=INTERFACE_NS)
            if neighborhood_bfd_obj is not None:
              neighborhood_bfd_tx = None
              neighborhood_bfd_tx_obj = neighborhood_bfd_obj.find('interface-config:desired-tx-interval', namespaces=INTERFACE_NS)
              if neighborhood_bfd_tx_obj is not None:
                neighborhood_bfd_tx = neighborhood_bfd_tx_obj.text
              neighborhood_bfd_rx = None
              neighborhood_bfd_rx_obj = neighborhood_bfd_obj.find('interface-config:required-min-rx-interval', namespaces=INTERFACE_NS)
              if neighborhood_bfd_rx_obj is not None:
                neighborhood_bfd_rx = neighborhood_bfd_rx_obj.text
              neighborhood_bfd_echo = None
              neighborhood_bfd_echo_obj = neighborhood_bfd_obj.find('interface-config:required-min-echo-interval', namespaces=INTERFACE_NS)
              if neighborhood_bfd_echo_obj is not None:
                neighborhood_bfd_echo = neighborhood_bfd_echo_obj.text
              neighborhood_bfd_link_interval = None
              neighborhood_bfd_link_interval_obj = neighborhood_bfd_obj.find('interface-config:link-test-interval', namespaces=INTERFACE_NS)
              if neighborhood_bfd_link_interval_obj is not None:
                neighborhood_bfd_link_interval = neighborhood_bfd_link_interval_obj.text
              neighborhood_bfd_link_length = None
              neighborhood_bfd_link_length_obj = neighborhood_bfd_obj.find('interface-config:link-test-length', namespaces=INTERFACE_NS)
              if neighborhood_bfd_link_length_obj is not None:
                neighborhood_bfd_link_length = neighborhood_bfd_link_length_obj.text
              neighborhood_bfd_authentication = None
              neighborhood_bfd_authentication_obj = neighborhood_bfd_obj.find('interface-config:authentication-type', namespaces=INTERFACE_NS)
              if neighborhood_bfd_authentication_obj is not None:
                neighborhood_bfd_authentication = neighborhood_bfd_authentication_obj.text
              neighborhood_bfd_multiplier = None
              neighborhood_bfd_multiplier_obj = neighborhood_bfd_obj.find('interface-config:multiplier', namespaces=INTERFACE_NS)
              if neighborhood_bfd_multiplier_obj is not None:
                neighborhood_bfd_multiplier = neighborhood_bfd_multiplier_obj.text
              neighborhood_bfd_state = None
              neighborhood_bfd_state_obj = neighborhood_bfd_obj.find('interface-config:state', namespaces=INTERFACE_NS)
              if neighborhood_bfd_state_obj is not None:
                neighborhood_bfd_state = neighborhood_bfd_state_obj.text
              neighborhood_bfd = {}
              neighborhood_bfd['desired-tx-interval'] = neighborhood_bfd_tx
              neighborhood_bfd['required-min-rx-interval'] = neighborhood_bfd_rx
              neighborhood_bfd['required-min-echo-interval'] = neighborhood_bfd_echo
              neighborhood_bfd['link-test-interval'] = neighborhood_bfd_link_interval
              neighborhood_bfd['link-test-length'] = neighborhood_bfd_link_length
              neighborhood_bfd['authentication-type'] = neighborhood_bfd_authentication
              neighborhood_bfd['multiplier'] = neighborhood_bfd_multiplier
              neighborhood_bfd['state'] = neighborhood_bfd_state
            neighborhood_map['topology'] = neighborhood_topology
            neighborhood_map['external-nat-address'] = neighborhood_ext_nat
            neighborhood_map['qp-value'] = neighborhood_qp
            neighborhood_map['bfd'] = neighborhood_bfd
            ni_neighborhoods[neighborhood_name] = neighborhood_map
          ni_map['neighborhoods'] = ni_neighborhoods
          try:
            address = network_interface.find('interface-config:address', namespaces=INTERFACE_NS)
            ip_address = address.find('interface-config:ip-address', namespaces=INTERFACE_NS).text
          except AttributeError:
            ip_address = 'dhcp'
          ni_map['ip-address'] = ip_address
          di_map[ni_name] = ni_map
        node_map[device_id] = di_map
      router_map[node_name] = node_map
    authority_map[router_name]= router_map
  return authority_map

def _generate_adjacency_changes_map(authority_map, target_router, leases, delete):
  target_router_neighborhoods = {}
  target_router_map = authority_map[target_router]
  for node, node_map in target_router_map.iteritems():
    for device_interface, di_map in node_map.iteritems():
      for network_interface, ni_map in di_map.iteritems():
        neighborhoods = ni_map['neighborhoods']
        adjacencies = ni_map['adjacencies']
        ip_address = ni_map['ip-address']
        if ip_address == 'dhcp':
          ip_address = leases.get(network_interface)
        if ip_address:
          if neighborhoods:
            target_router_neighborhoods[ip_address] = neighborhoods
  adjacency_change_map = {}
  for router, router_map in authority_map.iteritems():
    if ( router != target_router ):
      router_change_map = {}
      for node, node_map in router_map.iteritems():
        node_change_map = {}
        for device_interface, di_map in node_map.iteritems():
          di_change_map = {}
          for network_interface, ni_map in di_map.iteritems():
            ni_change_map = {}
            adj_add = {}
            adj_delete = []
            ni_sec = ni_map.get('inter-router-security')
            neighborhoods = ni_map['neighborhoods']
            adjacencies = ni_map['adjacencies']
            for adjacency_ip, adjacency_peer in adjacencies.iteritems():
              if adjacency_peer == target_router:
                if adjacency_ip == delete:
                  logger.info("Adjacency {4} matches the targeted delete IP:{0}.{1}.{2}.{3}".format(router,node,device_interface,network_interface, adjacency_ip))
                  adj_delete.append(adjacency_ip)
            for target_adjacency_ip, target_neighborhoods in target_router_neighborhoods.iteritems():
              for target_neighborhood in target_neighborhoods:
                if target_neighborhood in neighborhoods.keys():
                  if neighborhoods[target_neighborhood].get('topology') == 'hub':
                    if target_adjacency_ip not in adjacencies.keys():
                      logging.info("Adjacency {0} should be added to {1}.{2}.{3}.{4}".format(target_adjacency_ip,router,node,device_interface,network_interface))
                      new_adj = {}
                      new_adj['peer'] = target_router
                      new_adj['inter-router-security'] = ni_sec
                      if neighborhoods[target_neighborhood].get('external-nat-address'):
                        new_adj['external-nat-address'] = neighborhoods[target_neighborhood].get('external-nat-address')
                      if neighborhoods[target_neighborhood].get('qp-value'):
                        new_adj['qp-value'] = neighborhoods[target_neighborhood].get('qp-value')
                      if neighborhoods[target_neighborhood].get('bfd'):
                        new_adj['bfd'] = neighborhoods[target_neighborhood].get('bfd')
                      adj_add[target_adjacency_ip] = new_adj
            if adj_add:
              ni_change_map['add'] = adj_add
            if adj_delete:
              ni_change_map['delete'] = adj_delete
            if ni_change_map:
              di_change_map[network_interface] = ni_change_map
          if di_change_map:
            node_change_map[device_interface] = di_change_map
        if node_change_map:
          router_change_map[node] = node_change_map
      if router_change_map:
        adjacency_change_map[router] = router_change_map
  return adjacency_change_map

def _adjacency_change_map_to_config_text(adjacency_change_map):
  adjacency_config_changes_string = "config\n    authority\n"
  for router, router_map in adjacency_change_map.iteritems():
    adjacency_config_changes_string += "        router    {0}\n            name  {0}\n".format(router)
    for node, node_map in router_map.iteritems():
      adjacency_config_changes_string += "            node                  {0}\n".format(node) + \
                                         "                name              {0}\n".format(node)
      for di, di_map in node_map.iteritems():
        adjacency_config_changes_string += "                device-interface  {0}\n".format(di) + \
                                           "                    id            {0}\n".format(di)
        for ni, ni_map in di_map.iteritems():
          adjacency_config_changes_string += "                    network-interface    {0}\n".format(ni) + \
                                             "                        name             {0}\n".format(ni)
          adj_add = ni_map.get('add')
          adj_delete = ni_map.get('delete')
          if adj_delete:
            for adjacency in adj_delete:
              adjacency_config_changes_string += "                        delete adjacency     {0}\n".format(adjacency) + \
                                                 "                           ip-address          {0}\n".format(adjacency) + \
                                                 "                        exit\n"
          if adj_add:
            for adj_ip, adjacency in adj_add.iteritems():
              adj_peer = adjacency.get('peer')
              adj_sec = adjacency.get('inter-router-security')
              adj_nat = adjacency.get('external-nat-address')
              adj_qp = adjacency.get('qp-value')
              adj_sec = adjacency.get('inter-router-security')
              adj_bfd = adjacency.get('bfd')
              adjacency_config_changes_string += "                        adjacency     {0}\n".format(adj_ip) + \
                                                 "                           ip-address             {0}\n".format(adj_ip) + \
                                                 "                           peer                   {0}\n".format(adj_peer)
              if adj_sec:
                adjacency_config_changes_string += "                           inter-router-security  {0}\n".format(adj_sec)
              if adj_nat:
                adjacency_config_changes_string += "                           external-nat-address   {0}\n".format(adj_nat)
              if adj_qp:
                adjacency_config_changes_string += "                           qp-value               {0}\n".format(adj_qp)
              if adj_bfd:
                adjacency_config_changes_string += "                             bfd\n"
                adj_bfd_tx = adj_bfd['desired-tx-interval']
                if adj_bfd_tx:
                  adjacency_config_changes_string += "                               desired-tx-interval         {0}\n".format(adj_bfd_tx)
                adj_bfd_rx = adj_bfd['required-min-rx-interval']
                if adj_bfd_rx:
                  adjacency_config_changes_string += "                               required-min-rx-interval    {0}\n".format(adj_bfd_rx)
                adj_bfd_echo = adj_bfd['required-min-echo-interval']
                if adj_bfd_echo:
                  adjacency_config_changes_string += "                               required-min-echo-interval  {0}\n".format(adj_bfd_echo)
                adj_bfd_link_interval = adj_bfd['link-test-interval']
                if adj_bfd_link_interval:
                  adjacency_config_changes_string += "                               link-test-interval          {0}\n".format(adj_bfd_link_interval)
                adj_bfd_authentication = adj_bfd['authentication-type']
                if adj_bfd_authentication:
                  adjacency_config_changes_string += "                               authentication-type         {0}\n".format(adj_bfd_authentication)
                adj_bfd_link_length = adj_bfd['link-test-length']
                if adj_bfd_link_length:
                  adjacency_config_changes_string += "                               link-test-length            {0}\n".format(adj_bfd_link_length)
                adj_bfd_multiplier = adj_bfd['multiplier']
                if adj_bfd_multiplier:
                  adjacency_config_changes_string += "                               multiplier                  {0}\n".format(adj_bfd_multiplier)
                adj_bfd_state = adj_bfd['state']
                if adj_bfd_state:
                  adjacency_config_changes_string += "                               state                       {0}\n".format(adj_bfd_state)
                adjacency_config_changes_string += "                             exit\n"
              adjacency_config_changes_string += "                        exit\n"
          adjacency_config_changes_string += "                    exit\n"
        adjacency_config_changes_string += "                exit\n"
      adjacency_config_changes_string += "            exit\n"
    adjacency_config_changes_string += "        exit\n"
  adjacency_config_changes_string += "    exit\nexit\n"
  return adjacency_config_changes_string

class ncclientAgent(object):

    def __init__(self, ncclient_manager):
        self.netconf_session = ncclient_manager

    def editConfig(self, target_config, config_xml):
        edit_status = self.netconf_session.edit_config(target=target_config, config=config_xml)
        return edit_status

    def replaceConfig(self, target_config, config_xml):
        replace_status = self.netconf_session.edit_config(target=target_config, config=config_xml, default_operation="replace")
        return replace_status

    def removeConfig(self, target_config, config_xml):
        remove_status = self.netconf_session.delete_config(source=config_xml, target=target_config)
        return remove_status

    def commitConfig(self, validationType='distributed'):
        if validationType == 'distributed':
          commit_status = self.netconf_session.commit()
        else:
          commit_command = etree.Element('{urn:ietf:params:xml:ns:netconf:base:1.0}commit', {'nc':'urn:ietf:params:xml:ns:netconf:base:1.0'})
          vt = etree.Element('{urn:128technology:netconf:validate-type:1.0}validation-type', {'vt':'urn:128technology:netconf:validate-type:1.0'})
          vt.text = validationType
          commit_command.append(vt)
          commit_status = self.netconf_session.dispatch(commit_command)
        self.netconf_session.close_session()
        return commit_status


class t128Configurator(object):

    def __init__(self, config_agent):
        self.config_agent = config_agent

    def config(self, candidate_config_xml, state):
        action_status = "None"
        if state == "edit":
            action_status = self.config_agent.editConfig("candidate", candidate_config_xml)
        if state == "replace":
            action_status = self.config_agent.replaceConfig("candidate", candidate_config_xml)

        return action_status

    def commit(self, validationType='distributed'):
        commit_status = self.config_agent.commitConfig(validationType=validationType)
        return commit_status

def _commit_config_xml(config_xml, t128_host='127.0.0.1', t128_port='830', t128_user='admin', t128_publickey='/etc/128technology/ssh/pdc_ssh_key', validationType='distributed'):
    netconf_session = manager.connect(host=t128_host, port=t128_port, username=t128_user, key_filename=t128_publickey,
                                          allow_agent=True, look_for_keys=False, hostkey_verify=False)

    ncclient_agent = ncclientAgent(netconf_session)
    t128_configurator = t128Configurator(ncclient_agent)
    config_status = t128_configurator.config(config_xml, 'edit')

    if config_status.ok:
        commit_status = t128_configurator.commit(validationType=validationType)
        if commit_status.ok:
            print "Configuration committed successfully"
        else:
            print "There was an error committing the config"
    else:
        print "There was an error adding the candidate config"

def add_router(template_name, router_name, validationType='distributed'):
  logger.info("Adding config for router {0} using template {1}".format(router_name, template_name))
  add_config = _create_add_config(template_name, router_name)
  if add_config:
    logger.debug("Rendered add router config: {0}".format(add_config))
    cc = Config.Config()
    cc.load_t128_config_model('/var/model/consolidatedT128Model.xml')
    add_config_xml = cc.convert_config_to_netconf_xml(add_config.split('\n'))
    return _commit_config_xml(add_config_xml, validationType=validationType)
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
    return _commit_config_xml(delete_config_xml, validationType=validationType)
  else:
    ret = Returner(returner='saltstack', name="delete_router", changes={}, result=False, comment="Could not find a router by the given name")
    return ret.getReturn()


def update_adjacencies(target_router, leases, delete):
  if leases or delete:
    logger.info("Updating adjacencies for %s with leases: %s and delete %s", target_router, leases, delete)
    authority_map = _get_authority_map()
    logger.debug("Generated authority map: %s", authority_map)
    adjacency_change_map = _generate_adjacency_changes_map(authority_map, target_router, leases, delete)
    logger.debug("Generated adjacency change map: %s", adjacency_change_map)
    if adjacency_change_map:
      adjacency_change_config_text = _adjacency_change_map_to_config_text(adjacency_change_map)
      logger.debug("Rendered adjacency change config: %s", adjacency_change_config_text)
      cc = Config.Config()
      cc.load_t128_config_model('/var/model/consolidatedT128Model.xml')
      adjacency_change_config_xml = cc.convert_config_to_netconf_xml(adjacency_change_config_text.split('\n'))
      return _commit_config_xml(adjacency_change_config_xml, validationType='local')
    else:
      ret = Returner(returner='saltstack', name="update_adjacencies", changes={}, result=True, comment="No adjacency changes need to be applied")
      return ret.getReturn()
  else:
    logger.debug("Router {0} send empty data".format(target_router))
    return None
