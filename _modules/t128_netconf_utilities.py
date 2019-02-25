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
handler = logging.FileHandler('{0}/{1}.log'.format(LOG_DIRECTORY,'t128_netconf_utilities'))
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

class t128ConfigHelper(object):
  def get_current_config_xml(self, host='127.0.0.1', port='830', username='admin', key_filename='/home/admin/.ssh/pdc_ssh_key'):
    with manager.connect(host=host, port=port, username=username, key_filename=key_filename, allow_agent=True, look_for_keys=False, hostkey_verify=False) as m:
      c = m.get_config(source='running').data
    return c.find('t128:config', namespaces=T128_NS)

  def commit_config_xml(self, config_xml, t128_host='127.0.0.1', t128_port='830', t128_user='admin', t128_publickey='/home/admin/.ssh/pdc_ssh_key', validationType='distributed', commit_timeout=90):
      netconf_session = manager.connect(host=t128_host, port=t128_port, username=t128_user, 
          key_filename=t128_publickey, allow_agent=True, look_for_keys=False, hostkey_verify=False, timeout=commit_timeout)

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
