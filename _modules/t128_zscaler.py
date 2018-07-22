#!/usr/bin/python
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import json
import string
import random
import time
import t128_netconf_utilities
import platform
from lxml import etree

DEFAULT_VPN_NAME = 'zscaler'
PILLAR_DIRECTORY = '/srv/pillar'
IKE        ='aes128-sha1;MODP1024'
PHASE2ALG  ='null-md5;MODP1024'
IKELIFETIME='120m'
SALIFETIME ='30m'

def _generate_random_psk(length=64,chars=string.letters + string.digits):
    return ''.join(random.choice(chars) for _ in range(length))

def _obfuscateApiKey(apiKey):
    now = str(long(time.time() * 1000))
    n = now[-6:]
    r = str(int(n) >> 1).zfill(6)
    obfuscatedApiKey = ""
    for i in range(0, len(n), 1):
        obfuscatedApiKey += apiKey[int(n[i])]
    for j in range(0, len(r), 1):
        obfuscatedApiKey += apiKey[int(r[j])+2]
    return obfuscatedApiKey, now

def _create_asset_map(config_xml):
  authority = config_xml.find('authority-config:authority', namespaces=t128_netconf_utilities.AUTHORITY_NS)
  router_map = {}
  routers = authority.findall('authority-config:router', namespaces=t128_netconf_utilities.AUTHORITY_NS)
  for router in routers:
    router_name = router.find('authority-config:name', namespaces=t128_netconf_utilities.AUTHORITY_NS).text
    nodes = router.findall('system-config:node', namespaces=t128_netconf_utilities.SYSTEM_NS)
    node_map = {}
    for node in nodes:
      node_name = node.find('system-config:name', namespaces=t128_netconf_utilities.SYSTEM_NS).text
      asset = node.find('system-config:asset-id', namespaces=t128_netconf_utilities.SYSTEM_NS).text
      node_map[node_name] = asset
    router_map[router_name] = node_map
  return router_map

def _create_minion_pillar(vpn_name, userfqdn, psk, host1, host2):
  zscaler_vpn_pillar = "ipsec_vpns:\n"
  zscaler_vpn_pillar+= "  {}:\n".format(vpn_name)
  zscaler_vpn_pillar+= "  - right: '{}'\n".format(host1)
  zscaler_vpn_pillar+= "    ike: '{}'\n".format(IKE)
  zscaler_vpn_pillar+= "    phase2alg: '{}'\n".format(PHASE2ALG)
  zscaler_vpn_pillar+= "    ikelifetime: '{}'\n".format(IKELIFETIME)
  zscaler_vpn_pillar+= "    salifetime: '{}'\n".format(SALIFETIME)
  zscaler_vpn_pillar+= "    psk: '{}'\n".format(psk)
  zscaler_vpn_pillar+= "    leftid: \'{}\'\n".format(userfqdn)
  zscaler_vpn_pillar+= "    metric: 100\n"
  zscaler_vpn_pillar+= "  - right: '{}'\n".format(host2)
  zscaler_vpn_pillar+= "    ike: '{}'\n".format(IKE)
  zscaler_vpn_pillar+= "    phase2alg: '{}'\n".format(PHASE2ALG)
  zscaler_vpn_pillar+= "    ikelifetime: '{}'\n".format(IKELIFETIME)
  zscaler_vpn_pillar+= "    salifetime: '{}'\n".format(SALIFETIME)
  zscaler_vpn_pillar+= "    psk: '{}'\n".format(psk)
  zscaler_vpn_pillar+= "    leftid: \'{}\'\n".format(userfqdn)
  zscaler_vpn_pillar+= "    metric: 200"
  return zscaler_vpn_pillar

def zscaler_configure(username, password, apiKey):
  zscaler_data = __pillar__['zscaler_data']
  zscaler_base_uri = "https://{}/api/v1".format(zscaler_data['zscaler_uri'])
  obfApiKey, timestamp = _obfuscateApiKey(apiKey)
  headers = {
    'Content-Type': "application/json",
    'Cache-Control': "no-cache",
  }
  payload = {"username":username,"password":password,"apiKey": obfApiKey, "timestamp": timestamp}
  s = requests.session()
  # Zscaler wants 1 request per second so we can expect occassional 429 responses from them.
  # Handle this automatically
  retries = Retry(total=5, backoff_factor=1,status_forcelist=[429,502,503,504],method_whitelist=frozenset(['GET','POST']))
  s.mount('https://', HTTPAdapter(max_retries=retries))
  login = s.post("{0}/authenticatedSession".format(zscaler_base_uri), headers=headers, data=json.dumps(payload))
  if (login.status_code >= 400 or login.status_code < 200):
    return "Error authenticating to Zscaler: {0}: {1}".format(login.status_code, login.json())
  zdomain = zscaler_data['domain_name']
  zscaler_routers = zscaler_data['routers']
  ch = t128_netconf_utilities.t128ConfigHelper()
  config_xml = ch.get_current_config_xml()
  router_map = _create_asset_map(config_xml)
  zscaler_top = "base:\n"
  __salt__['file.mkdir']("{0}/{1}".format(PILLAR_DIRECTORY,'zscaler'))
  ret_string = ""
  for router, nodes in zscaler_routers.iteritems():
    vpns = []
    for node, tunnels in nodes.iteritems():
      psk = _generate_random_psk()
      userfqdn =  "{0}@{1}".format(node,zdomain)
      vpnPayload = {
        "type": "UFQDN",
        "fqdn": userfqdn,
        "comments": "Created automatically",
        "preSharedKey": psk
      }
      vpn = s.post("{0}/vpnCredentials".format(zscaler_base_uri), headers=headers, data=json.dumps(vpnPayload))
      if vpn.status_code == 200:
        vpns.append({"id":  vpn.json()['id'],"type": "UFQDN"})
        vpn_name = tunnels.get('vpn_name')
        if vpn_name is None:
          vpn_name = DEFAULT_VPN_NAME
        node_pillar = _create_minion_pillar(vpn_name, userfqdn, psk, tunnels['vpn_host1'], tunnels['vpn_host2'])
        __salt__['file.write']("{0}/zscaler/{1}.sls".format(PILLAR_DIRECTORY,node),args=node_pillar)
        zscaler_top += "  \'{}\':\n".format(router_map[router][node])
        # We use this matching because glob matching will conflict with the main top states
        zscaler_top += "    - match: grain\n"
        zscaler_top += "    - zscaler.{}\n".format(node)
        ret_string += "VPNs and pillar data successfully created for node {}\n".format(node)
      elif vpn.status_code == 409:
        zscaler_top += "  \'id:{}\':\n".format(router_map[router][node])
        zscaler_top += "    - match: grain\n"
        zscaler_top += "    - zscaler.{}\n".format(node)
        ret_string += "VPN already configured for node {0}, not re-writing pillar data, but keeping in top file.\n".format(node)
      else:
        ret_string += "Unhandled error adding VPN for node {0} not writing pillar data.  Error code: {1}: {2}\n".format(node,vpn.status_code,vpn.json())
    if len(vpns) > 0:
      locationPayload = {
        "name": router,
        "vpnCredentials": vpns
      }
      location = s.post("{0}/locations".format(zscaler_base_uri), headers=headers, data=json.dumps(locationPayload))
      if location.status_code == 200:
        ret_string += "Location {0} added successfully.\n".format(router)
      elif location.status_code == 409:
        ret_string += "Location {0} already existed in Zscaler.\n".format(router)
      else:
        ret_string += "Unhandled error adding location {0}.  Error code: {1}: {2}\n".format(router,location.status_code,location.json())
    else:
      ret_string += "No new VPNs created, not attempting to add location {}".format(router)
  __salt__['file.write']("{0}/zscaler-top.sls".format(PILLAR_DIRECTORY),args=zscaler_top)
  return ret_string
