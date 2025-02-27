import typing
from box import Box
from netsim.utils import log
from netsim import api,data
from netsim.augment import devices
import os

import requests
import json
import time
import requests.packages.urllib3 as urllib3
urllib3.disable_warnings()

# Global variables
_config_name = 'netbrain'
NETBRAIN_TOKEN = ""

def topology_expand(topology: Box) -> None:
  create_map = topology.get('defaults.netbrain.create_map', True)
  expand_topology = topology.get('defaults.netbrain.expand_topology',"no")

  if not create_map and expand_topology=="no":
    return

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
  create_map = topology.get('defaults.netbrain.create_map', True)
  if not create_map:
    return
  expand_topology = topology.get('defaults.netbrain.expand_topology',"no")
  netbrain_create_map(topology,expand_topology)

def netbrain_create_map(topology: Box, expand_topology: str) -> None:
  global NETBRAIN_TOKEN
  global _config_name

  api_url = topology.get('defaults.netbrain.api_url')
  api_user = topology.get('defaults.netbrain.api_user')
  api_stub = topology.get('defaults.netbrain.api_stub')

  headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
  headers["Token"] = NETBRAIN_TOKEN

  # Determine the first tenant/domain that {api_user} is setup with, ideally only one of each
  users_url = api_url + f"/ServicesAPI/API/V1/CMDB/Users?username={api_user}"
  try:
    users_result = requests.get(users_url, headers=headers, verify=False)
    users_result.raise_for_status()
    users = users_result.json()["UserData"][0]["TenantAndRole"][0]
    tenant_id = users["tenantId"]
    domain_id = users["domains"][0]["id"]
    devices = [ name for name, node in topology.nodes.items() ]

    CREATE_MAP_BODY = {
      'domain_setting': {
          'tenant_id': tenant_id,
          'domain_id': domain_id
      },
      'basic_setting': {
          'user_id': api_user, # can not be null.
          'stub_name': api_stub, # can not be null.
          'triggered_by': api_user # can not be null.
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
    map_result = requests.post(create_map_url, data=json.dumps(CREATE_MAP_BODY), headers=headers, verify=False)
    map_result.raise_for_status()
    map = map_result.json()
    if 'error' in map:
      log.error(f"Error creating map: {map['error']}",log.FatalError,_config_name)
    else:
      log.info(f"Netbrain plugin: Map {map['mapName']} created for {len(devices)} nodes at {api_url}/{map['mapUrl']}")
  except requests.exceptions.HTTPError as err:
    log.error( f"Error accessing Netbrain API at {api_url} as user {api_user}: {err}",
      log.FatalError,
      _config_name)
