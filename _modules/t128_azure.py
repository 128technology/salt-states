#!/usr/bin/python

import os
import jinja2
import jinja2.exceptions
import json
import logging
import requests
import salt.client

try:
  import adal
  import t128_netconf_utilities
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

MASTER_CONFIG = '/etc/128technology/salt/master'
PILLAR_DIRECTORY = '/srv/pillar'
AZURE_PILLAR_DIRECTORY = 'azure-virtual-wan'

IKE        ='aes128-sha1;MODP1024'
PHASE2ALG  ='aes128-sha1;MODP1024'
IKELIFETIME='3600'
SALIFETIME ='28800'

IPSEC_INT_NAME = 'sfc-ipsec'
IPSEC_TENANT = 'ipsec'
IPSEC_ADDRESS = '169.254.31.1'
IPSEC_PREFIX = '30'
IPSEC_GATWAY = '169.254.31.2'
IPSEC_SERVICE_NAME = 'ipsec'
IPSEC_SERVICE_ADDRESSES = ['0.0.0.0/0']
IPSEC_SR_NAME = 'ipsec'

AZURE_KNI_ADDRESS = '169.254.31.5'
AZURE_KNI_PREFIX = '30'
AZURE_KNI_GATEWAY = '169.254.31.6'

VWAN_NEIGHBORHOOD_TAG = 'neighborhood'
VWAN_TENANT_TAG = 'tenant'
VWAN_SVC_AND_INT_TAG = 't128-name'
VWAN_SAS_URL_TAG = 'sas-url'

if not os.path.exists(LOG_DIRECTORY):
    os.makedirs(LOG_DIRECTORY)
logger = logging.getLogger(__name__)
handler = logging.FileHandler('{0}/{1}.log'.format(LOG_DIRECTORY,'t128_azure'))
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

def _get_current_config(host='127.0.0.1', port='830', username='admin', key_filename='/home/admin/.ssh/pdc_ssh_key'):
  with manager.connect(host=host, port=port, username=username, key_filename=key_filename, allow_agent=True, look_for_keys=False, hostkey_verify=False) as m:
    c = m.get_config(source='running').data
  return c.find('t128:config', namespaces=t128_netconf_utilities.T128_NS)

def _get_site_map(config_xml, neighborhood_key):
  site_map = {}
  authority = config_xml.find('authority-config:authority', namespaces=t128_netconf_utilities.AUTHORITY_NS)
  routers = authority.findall('authority-config:router', namespaces=t128_netconf_utilities.AUTHORITY_NS)
  for router in routers:
    router_map = {}
    router_address = ''
    router_name = router.find('authority-config:name', namespaces=t128_netconf_utilities.AUTHORITY_NS).text
    nodes = router.findall('system-config:node', namespaces=t128_netconf_utilities.SYSTEM_NS)
    for node in nodes:
      node_name = node.find('system-config:name', namespaces=t128_netconf_utilities.SYSTEM_NS).text
      asset_id = node.find('system-config:asset-id', namespaces=t128_netconf_utilities.SYSTEM_NS)
      device_interfaces = node.findall('system-config:device-interface', namespaces=t128_netconf_utilities.SYSTEM_NS)
      for device_interface in device_interfaces:
        network_interfaces = device_interface.findall('interface-config:network-interface', namespaces=t128_netconf_utilities.INTERFACE_NS)
        for network_interface in network_interfaces:
          ni_name = network_interface.find('interface-config:name', namespaces=INTERFACE_NS).text
          ni_address = network_interface.find('interface-config:address', namespaces=t128_netconf_utilities.INTERFACE_NS)
          if ni_address is not None:
            router_address = ni_address.find('interface-config:ip-address', namespaces=t128_netconf_utilities.INTERFACE_NS).text
            ni_gateway = ni_address.find('interface-config:gateway',  namespaces=t128_netconf_utilities.INTERFACE_NS)
          neighborhoods = network_interface.findall('interface-config:neighborhood', namespaces=t128_netconf_utilities.INTERFACE_NS)
          for neighborhood in neighborhoods:
            neighborhood_name = neighborhood.find('interface-config:name', namespaces=t128_netconf_utilities.INTERFACE_NS).text
            if neighborhood_name == neighborhood_key:
              external_nat_address = neighborhood.find('interface-config:external-nat-address', namespaces=t128_netconf_utilities.INTERFACE_NS)
              if external_nat_address is not None:
                router_address = external_nat_address.text
              vector = neighborhood.find('interface-config:vector', namespaces=t128_netconf_utilities.INTERFACE_NS)
              if vector is not None:
                router_map['location'] = vector.text
              router_map['address'] = router_address
              router_map['node'] = node_name
              router_map['wan_interface'] = ni_name
              if ni_gateway is not None:
                router_map['wan_gateway'] = ni_gateway.text
              if asset_id is not None:
                router_map['asset'] = asset_id.text
              site_map[router_name] = router_map
  return site_map

def _get_address_space(config_xml, azure_tenant, site_name):
  address_space = []
  authority = config_xml.find('authority-config:authority', namespaces=AUTHORITY_NS)
  services = authority.findall('service-config:service', namespaces=SERVICE_NS)
  azure_services = {}
  for service in services:
    service_name = service.find('service-config:name', namespaces=SERVICE_NS).text
    service_addresses = service.findall('service-config:address', namespaces=SERVICE_NS)
    addresses = []
    for service_address in service_addresses:
      addresses.append(service_address.text)
    access_policies = service.findall('service-config:access-policy', namespaces=SERVICE_NS)  
    for access_policy in access_policies:
      source = access_policy.find('service-config:source', namespaces=SERVICE_NS).text
      if source == azure_tenant:
        azure_services[service_name] = addresses
  routers = authority.findall('authority-config:router', namespaces=AUTHORITY_NS)
  for router in routers:
    router_name = router.find('authority-config:name', namespaces=AUTHORITY_NS).text
    if router_name == site_name:
      service_routes = router.findall('service-config:service-route', namespaces=SERVICE_NS)
      for service_route in service_routes:
        # We don't want to include address space for peer service-routes, just next hops
        next_hop = service_route.findall('service-config:next-hop', namespaces=SERVICE_NS)
        if next_hop:
          sr_service = service_route.find('service-config:service-name', namespaces=SERVICE_NS).text
          if sr_service in azure_services.keys():
            address_space = address_space + azure_services[sr_service]
  address_space = list(set(address_space))
  # TODO: Find overlaps and supersets
  return address_space

def _create_minion_pillar(vpn_name, psk, public_addr, host1, host2):
  vpn_pillar = "ipsec_vpns:\n"
  vpn_pillar+= "  {}:\n".format(vpn_name)
  vpn_pillar+= "  - right: '{}'\n".format(host1)
  vpn_pillar+= "    ike: '{}'\n".format(IKE)
  vpn_pillar+= "    phase2alg: '{}'\n".format(PHASE2ALG)
  vpn_pillar+= "    ikelifetime: '{}'\n".format(IKELIFETIME)
  vpn_pillar+= "    salifetime: '{}'\n".format(SALIFETIME)
  vpn_pillar+= "    psk: '{}'\n".format(psk)
  vpn_pillar+= "    leftid: \'{}\'\n".format(public_addr)
  vpn_pillar+= "    metric: 100\n"
  vpn_pillar+= "  - right: '{}'\n".format(host2)
  vpn_pillar+= "    ike: '{}'\n".format(IKE)
  vpn_pillar+= "    phase2alg: '{}'\n".format(PHASE2ALG)
  vpn_pillar+= "    ikelifetime: '{}'\n".format(IKELIFETIME)
  vpn_pillar+= "    salifetime: '{}'\n".format(SALIFETIME)
  vpn_pillar+= "    psk: '{}'\n".format(psk)
  vpn_pillar+= "    leftid: \'{}\'\n".format(public_addr)
  vpn_pillar+= "    metric: 200\n"
  return vpn_pillar

def _config_snippet_generate(router_name=None, node_name=None, interface_name=None, tenant=None, interface_address=None, interface_prefix=None, interface_gateway=None, service_name=None, service_addresses=None, access_tenant=None, sr_name=None, sr_node_name=None, sr_interface_name=None, sr_gateway=None):
  config  = ""
  if router_name:
    config += "        router    {}\n".format(router_name)
    config += "            name                 {}\n".format(router_name)
    if node_name:
      config += "            node                 {}\n".format(node_name)
      config += "                name              {}\n".format(node_name)
      config += "                device-interface  {}\n".format(interface_name)
      config += "                    name               {}\n".format(interface_name)
      config += "                    type               host\n"
      config += "                    network-interface  {}\n".format(interface_name)
      config += "                        name       {}\n".format(interface_name)
      config += "                        tenant     {}\n".format(tenant)
      config += "                        address    {}\n".format(interface_address)
      config += "                            ip-address     {}\n".format(interface_address)
      config += "                            prefix-length  {}\n".format(interface_prefix)
      config += "                            gateway        {}\n".format(interface_gateway)
      config += "                        exit\n"
      config += "                    exit\n"
      config += "                exit\n"
      config += "            exit\n"
    if sr_name:
      config += "            service-route        {}\n".format(sr_name)
      config += "                name          {}\n".format(sr_name)
      config += "                service-name  {}\n".format(service_name)
      config += "                next-hop      {0} {1}\n".format(sr_node_name,sr_interface_name)
      config += "                    node-name   {}\n".format(sr_node_name)
      config += "                    interface   {}\n".format(sr_interface_name)
      if sr_gateway:
        config += "                    gateway-ip  {}\n".format(sr_gateway)
      config += "                exit\n"
      config += "            exit\n"
    config += "        exit\n"
  if tenant:
    config += "        tenant    {}\n".format(tenant)
    config += "            name  {}\n".format(tenant)
    config += "        exit\n"
  if service_name:
    config += "        service            {}\n".format(service_name)
    config += "            name           {}\n".format(service_name)
    if service_addresses:
      for service_address in service_addresses:
        config += "            address        {}\n".format(service_address)
    if access_tenant:
      config += "            access-policy  {}\n".format(access_tenant)
      config += "                source  {}\n".format(access_tenant)
      config += "            exit\n"
    config += "            share-service-routes  false\n"
    config += "        exit\n"
  return config

class azureVwanHelper(object):
  AUTHENTICATION_ENDPOINT = 'https://login.microsoftonline.com/'
  RESOURCE_ENDPOINT = 'https://management.azure.com/'
  API_VERSION = '2018-04-01'

  def __init__(self):
    azure_settings = __pillar__['azureSettings']
    self.subscriptionId = azure_settings['subscriptionId']
    self.resourceGroup = azure_settings['resourceGroup']
    self.tenantId = azure_settings['tenantId']
    self.appId = azure_settings['appId']
    self.password = azure_settings['password']
    access_token = self._azure_authenticate()
    self.headers = {'Content-Type': 'application/json', 'Accept': 'application/json', 'Authorization': 'Bearer ' + access_token}

  def _azure_authenticate(self):
    context = adal.AuthenticationContext(self.AUTHENTICATION_ENDPOINT + self.tenantId)
    token_response = context.acquire_token_with_client_credentials(self.RESOURCE_ENDPOINT, self.appId, self.password)
    return token_response.get('accessToken')

  def get_vwan_map(self):
    vwan_uri = '{0}/subscriptions/{1}/resourceGroups/{2}/providers/Microsoft.Network/virtualWans/?api-version={3}'.format(self.RESOURCE_ENDPOINT, self.subscriptionId, self.resourceGroup, self.API_VERSION)
    vwan_resp = requests.get(vwan_uri, headers=self.headers)
    # TODO: Error handling logic
    vwans = vwan_resp.json()['value']
    vwan_map = {}
    for vwan in vwans:
      tags = vwan.get('tags')
      if tags:
        vv = {}
        neighborhood = tags.get(VWAN_NEIGHBORHOOD_TAG)
        if neighborhood:
          vv[VWAN_NEIGHBORHOOD_TAG] = neighborhood
        tenant = tags.get(VWAN_TENANT_TAG)
        if tenant:
          vv[VWAN_TENANT_TAG] = tenant
        t128name = tags.get(VWAN_SVC_AND_INT_TAG)
        if t128name:
          vv[VWAN_SVC_AND_INT_TAG] = t128name
        sas_url = tags.get(VWAN_SAS_URL_TAG)
        if sas_url:
          vv[VWAN_SAS_URL_TAG] = sas_url
        vwan_map[vwan['id']] = vv
    return vwan_map

  def does_site_exist(self, site_name):
    site_uri = '{0}/subscriptions/{1}/resourceGroups/{2}/providers/Microsoft.Network/vpnSites/{3}/?api-version={4}'.format(self.RESOURCE_ENDPOINT, self.subscriptionId, self.resourceGroup, site_name, self.API_VERSION)
    site_resp = requests.get(site_uri, headers=self.headers)
    # TODO: More rigorous testing
    if site_resp.status_code == 404:
      return False
    else:
      return True

  def add_site(self, site_name, site_details, virtual_wan_id, address_space):
    site_address_space = {}
    site_address_space['addressPrefixes'] = address_space
    virtual_wan = {}
    virtual_wan['id'] = virtual_wan_id
    site_properties = {}
    site_properties['virtualWAN'] = virtual_wan
    site_properties['ipAddress'] = site_details['address']
    site_properties['addressSpace'] = site_address_space
    site = {}
    site['properties'] = site_properties
    site['location'] = site_details['location']
    site_uri = '{0}/subscriptions/{1}/resourceGroups/{2}/providers/Microsoft.Network/vpnSites/{3}/?api-version={4}'.format(self.RESOURCE_ENDPOINT, self.subscriptionId, self.resourceGroup, site_name, self.API_VERSION)
    site_resp = requests.put(site_uri, headers=self.headers, data=json.dumps(site))
    # TODO: Validate
    return site_resp

  def get_vwan_conns(self, vwan, sas_url):
    # Get the sites that are part of this vwan
    site_uri = '{0}/subscriptions/{1}/resourceGroups/{2}/providers/Microsoft.Network/vpnSites?api-version={3}'.format(self.RESOURCE_ENDPOINT, self.subscriptionId, self.resourceGroup, self.API_VERSION)
    site_resp = requests.get(site_uri,headers=self.headers)
    # TODO: Error handling
    sites = site_resp.json()['value']
    site_ids = []
    for site in sites:
      if site['properties']['virtualWan']['id'] == vwan:
        site_ids.append(site['id'])
    
    # Request site data sent to SAS URL
    sas_del_resp = requests.delete(sas_url)
    vpn_body = {}
    vpn_body['vpnSites'] = site_ids
    vpn_body['outputBlobSasUrl'] = sas_url
    vwan_uri = '{0}{1}/vpnConfiguration?api-version={2}'.format(self.RESOURCE_ENDPOINT, vwan, self.API_VERSION)
    vwan_resp = requests.post(vwan_uri,headers=self.headers,data=json.dumps(vpn_body))
    site_connections = requests.get(sas_url)
    connections_by_site = {}
    if site_connections.ok and site_connections.text:
      for site_connection in site_connections.json():
        site_name = site_connection['vpnSiteConfiguration']['Name']
        site_address = site_connection['vpnSiteConfiguration']['IPAddress']
        # There should only be one connection, right?
        vpn_connection = site_connection['vpnSiteConnections'][0]
        psk = vpn_connection['connectionConfiguration']['PSK']
        gateway = vpn_connection['gatewayConfiguration']['IpAddresses']
        connection = {}
        connection['SiteAddress'] = site_address
        connection['PSK'] = psk
        connection['gateway'] = gateway
        connections_by_site[site_name] = connection
    return connections_by_site

  def get_vwan_address_space(self, vwan):
    vwan_uri = '{0}{1}?api-version={2}'.format(self.RESOURCE_ENDPOINT, vwan, self.API_VERSION)
    vwan_resp = requests.get(vwan_uri,headers=self.headers)
    # TODO: Error handling
    vhubs = vwan_resp.json()['properties']['virtualHubs']
    address_space = []
    for vhub in vhubs:
      vhub_uri = '{0}{1}?api-version={2}'.format(self.RESOURCE_ENDPOINT, vhub['id'], self.API_VERSION)
      vhub_resp = requests.get(vhub_uri,headers=self.headers)
      # TODO: Error handling
      address_space.append(vhub_resp.json()['properties']['addressPrefix'])
      vnets = vhub_resp.json()['properties']['virtualNetworkConnections']
      for vnet in vnets:
        vnet_uri = '{0}{1}?api-version={2}'.format(self.RESOURCE_ENDPOINT, vnet['id'], self.API_VERSION)
        vnet_resp = requests.get(vnet_uri, headers=self.headers)
        # TODO: Error handling
        remote_vnet_uri = '{0}{1}?api-version={2}'.format(self.RESOURCE_ENDPOINT, vnet_resp.json()['properties']['remoteVirtualNetwork']['id'], self.API_VERSION)
        remote_vnet_resp = requests.get(remote_vnet_uri, headers=self.headers)
        # TODO: Error handling
        remote_vnet_space = remote_vnet_resp.json()['properties']['addressSpace']['addressPrefixes']
        # Above returns a list of prefixes, append to our list
        address_space += remote_vnet_space
    return address_space
      
def validate_sites():
  logger.debug("Looking for new sites...")
  responses = {}
  config_xml = _get_current_config()
  vwh = azureVwanHelper()
  vwans = vwh.get_vwan_map()
  for vwan, vwan_data in vwans.iteritems():
    neighborhood = vwan_data[VWAN_NEIGHBORHOOD_TAG]
    tenant = vwan_data[VWAN_TENANT_TAG]
    logger.debug("Parsing config for neighborhood {0} associated with vwan {1}...".format(neighborhood, vwan))
    site_map = _get_site_map(config_xml, neighborhood)
    for site_name, site_details in site_map.iteritems():
      if not vwh.does_site_exist(site_name):
        address_space = _get_address_space(config_xml, tenant, site_name)
        logger.debug("Site {0} does not exist in Azure, attempting to add...".format(site_name))
        site_resp = vwh.add_site(site_name, site_details, vwan, address_space)
        responses[site_name] = "{}: {}".format(site_resp.status_code, site_resp.json())
  return responses

def orchestrate_vpns():
  logger.debug("Checking for new VPNs to orchestrate...")
  __salt__['file.mkdir']("{0}/{1}".format(PILLAR_DIRECTORY, AZURE_PILLAR_DIRECTORY))
  config_xml = _get_current_config()
  vwh = azureVwanHelper()
  vwans = vwh.get_vwan_map()
  azure_top = "base:\n"
  for vwan, vwan_data in vwans.iteritems():
    neighborhood = vwan_data[VWAN_NEIGHBORHOOD_TAG]
    azure_tenant = vwan_data[VWAN_TENANT_TAG]
    t128name = vwan_data[VWAN_SVC_AND_INT_TAG]
    sas_url = vwan_data[VWAN_SAS_URL_TAG]
    site_map = _get_site_map(config_xml, neighborhood)
    vwan_connections = vwh.get_vwan_conns(vwan,sas_url)
    vwan_address_space = vwh.get_vwan_address_space(vwan)
    for site_name, connection in vwan_connections.iteritems():
      site_details = site_map[site_name]
      changes = {}
      if site_map[site_name].get('asset'):
        vpn_data = _create_minion_pillar(t128name, connection['PSK'], connection['SiteAddress'], connection['gateway']['Instance0'], connection['gateway']['Instance1'])
        manage_results = __salt__['file.manage_file']("{0}/{1}/{2}.sls".format(PILLAR_DIRECTORY, AZURE_PILLAR_DIRECTORY, site_name), '', '', '', '', 'root', 'root', 644, '', 'base', False, contents=vpn_data)
        if manage_results['changes'] != {}:
          logger.debug("Wrote pillar for site {}, pillar data changed".format(site_name))
          changes[site_name] = site_details
        azure_top += "  \'id:{}\':\n".format(site_details['asset'])
        # We use this matching because glob matching will conflict with the main top states
        azure_top += "    - match: grain\n"
        azure_top += "    - {0}.{1}".format(AZURE_PILLAR_DIRECTORY, site_name)
      __salt__['file.write']("{0}/{1}-top.sls".format(PILLAR_DIRECTORY, AZURE_PILLAR_DIRECTORY), args=azure_top)
      saltMaster = salt.client.LocalClient(c_path=MASTER_CONFIG)
      config  = "config\n"
      config += "    authority\n"
      for site_name, site_details in changes.iteritems():
        # Make sure required modules are available
        sync_ret = saltMaster.cmd(site_details['asset'], 'saltutil.sync_all', ['saltenv=128T,base'])
        ipsec_sfc_ret = saltMaster.cmd(site_details['asset'], 'state.apply', ['setup-ipsec-sfc'])
        logger.debug("IPSec setup results:\n{}".format(ipsec_sfc_ret))
        ipsec_conn_ret = saltMaster.cmd(site_details['asset'], 'state.apply', ['setup-ipsec-connections'])
        logger.debug("IPSec connection setup:\n{}".format(ipsec_conn_ret))
        # Setup IPSec config
        ipsec_config = _config_snippet_generate(
          router_name=site_name, 
          node_name=site_details['node'], 
          interface_name=IPSEC_INT_NAME, 
          tenant=IPSEC_TENANT, 
          interface_address=IPSEC_ADDRESS, 
          interface_prefix=IPSEC_PREFIX, 
          interface_gateway=IPSEC_GATWAY, 
          service_name=IPSEC_SERVICE_NAME, 
          service_addresses=IPSEC_SERVICE_ADDRESSES, 
          access_tenant=IPSEC_TENANT, 
          sr_name=IPSEC_SR_NAME, 
          sr_node_name=site_details['node'], 
          sr_interface_name=site_details['wan_interface'], 
          sr_gateway=site_details.get('wan_gateway')
        )
        logger.debug("ipsec_config for site {0}:\n{1}".format(site_name,ipsec_config))
        azure_config = _config_snippet_generate(
          router_name=site_name, 
          node_name=site_details['node'], 
          interface_name=t128name, 
          tenant=azure_tenant, 
          interface_address=AZURE_KNI_ADDRESS, 
          interface_prefix=AZURE_KNI_PREFIX, 
          interface_gateway=AZURE_KNI_GATEWAY, 
          service_name=t128name, 
          service_addresses=vwan_address_space,
          sr_name=t128name, 
          sr_node_name=site_details['node'], 
          sr_interface_name=t128name, 
          sr_gateway=AZURE_KNI_GATEWAY
        )
        logger.debug("azure_config for site {0}:\n{1}".format(site_name,azure_config))
        config += ipsec_config 
        config += azure_config
        config += "    exit\n"
        config += "exit"
        ch = t128_netconf_utilities.t128ConfigHelper()
        cc = Config.Config()
        cc.load_t128_config_model('/var/model/consolidatedT128Model.xml')
        config_xml = cc.convert_config_to_netconf_xml(config.split('\n'))
        return ch.commit_config_xml(config_xml)
