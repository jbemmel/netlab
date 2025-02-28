import typing
from box import Box
from netsim.utils import log,files
from netsim import api,data
from netsim.augment import devices
import os

import requests
import json
import pathlib
import re

requests.packages.urllib3.disable_warnings()

_config_name = 'netbrain'

# Global variables
NETBRAIN_TOKEN = ""

def topology_expand(topology: Box) -> None:
  create_map = topology.get('defaults.netbrain.create_map',True)
  expand_topology = topology.get('defaults.netbrain.expand_topology',"no")

  # Check that env.NETBRAIN_TOKEN is available
  global NETBRAIN_TOKEN

  NETBRAIN_TOKEN = os.getenv('NETBRAIN_TOKEN')
  if not NETBRAIN_TOKEN:
    log.error( f"Environment variable 'NETBRAIN_TOKEN' must be defined with a valid Netbrain token",
      log.MissingValue,
      _config_name)
  log.info(f"Using Netbrain token {NETBRAIN_TOKEN} - create_map={create_map} expand_topology={expand_topology}")

'''
post_transform hook

Create a map of all nodes in the topology
'''
def post_transform(topology: Box) -> None:
  create_map = topology.get('defaults.netbrain.create_map',False)
  get_configs = topology.get('defaults.netbrain.get_config',True)
  if not (create_map or get_configs):
    return
  with requests.Session() as session:
    global NETBRAIN_TOKEN
    session.headers.update( {'Content-Type': 'application/json','Accept': 'application/json',
                             'Token': NETBRAIN_TOKEN } )
    if create_map:
      expand_topology = topology.get('defaults.netbrain.expand_topology',"no")
      netbrain_create_map(session,topology,expand_topology)

    get_configs = topology.get('defaults.netbrain.get_config',True)
    if get_configs:
      netbrain_get_configs(session,topology)

#############################################################################################

def netbrain_call_api(session: requests.Session, url: str, data: str = None) -> typing.Dict:
  global _config_name

  try:
    if data is None:
      result = session.get(url,verify=False)
    else:
      result = session.post(url,data=data,verify=False)
    result.raise_for_status()
    return result.json()
  except requests.exceptions.HTTPError as err:
    log.error( f"Error accessing Netbrain API at {url}: {err}",log.FatalError,_config_name)
    return {}

def netbrain_create_map(session: requests.Session, topology: Box, expand_topology: str) -> None:
  global _config_name

  api_url = topology.get('defaults.netbrain.api_url')
  api_user = topology.get('defaults.netbrain.api_user')

  # Determine the first tenant/domain that {api_user} is setup with, ideally only one of each
  users_url = api_url + f"/ServicesAPI/API/V1/CMDB/Users?username={api_user}"
  users_result = netbrain_call_api(session,users_url)
  if not users_result:
    return

  users = users_result["UserData"][0]["TenantAndRole"][0]
  tenant_id = users["tenantId"]
  domain_id = users["domains"][0]["id"]
  api_stub = topology.get('defaults.netbrain.api_stub')
  devices = [ name for name, node in topology.nodes.items() ]

  CREATE_MAP_BODY = {
    'domain_setting': {
        'tenant_id': tenant_id,
        'domain_id': domain_id
    },
    'basic_setting': {
        'user_id': api_user,     # can not be null.
        'stub_name': api_stub,   # can not be null.
        'triggered_by': "netlab" # can not be null.
    },
    'map_setting': {
        'map_create_mode': 9,
        'map_devices_para': {
          'devices' : devices,
          'auto_link': True,
          'auto_link_type': 'L2_Topo_Type',
          'include_neighbor': expand_topology != "no",
          'neighbor_type': f"{expand_topology}_Topo_Type" if expand_topology in ["L2","L3"] else ""
        }
    }
  }
  create_map_url = api_url + "/ServicesAPI/API/V1/Triggers/Run"
  map_result = netbrain_call_api(session,create_map_url,data=json.dumps(CREATE_MAP_BODY))
  if not map_result:
    return
  if 'error' in map_result:
    log.error(f"Error creating map: {map_result['error']}",log.FatalError,_config_name)
  else:
    log.info(f"Netbrain plugin: Map {map_result['mapName']} created for {len(devices)} nodes " +
             f"at {api_url}/{map_result['mapUrl']}")

def dellos10_clean_config(config: str):
    config = config.replace("\\r\\n","\r\n")

    # Remove config on ports 47-55 which get remapped
    for port in range(47,56):
      config = re.sub(f'interface ethernet1/1/{port}[^!]+!\r\n','',config)

    # Map ports 57-65 by -10 to 47-55
    config = re.sub(r'1/1/([5][7-9]|6[0-5])', lambda m: f"1/1/{int(m.group(1)) - 10}", config)

    # Remove login banner, interferes with CLI prompt logic on vrnetlab
    config = re.sub(r'banner[^\^]+\^[^\^]+\^C','', config)

    # Remove mgmt lines - they break ssh login
    config = re.sub(r'interface mgmt1/1/1[^!]+!\r\n','',config)

    return "!" + config

def netbrain_get_configs(session: requests.Session, topology: Box) -> None:
  api_url = topology.get('defaults.netbrain.api_url')
  for nodename, node in topology.nodes.items():
    if not node.get('netbrain.get_config',True) or node.get('unmanaged',False):
      continue
    config_url = api_url + f"/ServicesAPI/API/V1/CMDB/DataEngine/DeviceData/Configuration?hostname={nodename}"
    config = netbrain_call_api(session,config_url)
    if 'configuration' in config:
      out_folder = "netbrain_configs"
      pathlib.Path(out_folder).mkdir(parents=True, exist_ok=True)
      out_file = f"{out_folder}/{nodename}.config"
      if 'clab' in node:
        node.clab['startup-config'] = out_file
      else:
        out_file += ".j2"
        node.config = node.get('config',[]) + [ out_file ]

      config_str = config["configuration"]
      if node.device == "dellos10":
        config_str = dellos10_clean_config(config_str)
      files.create_file_from_text(out_file,config_str)
      log.info( f"Config for {nodename} saved under {out_file}" )
    else:
      log.error( f"Unable to get config for {nodename}: {config}",category=Warning )
