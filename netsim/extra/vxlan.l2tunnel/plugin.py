import typing
from box import Box
from netsim.utils import log
from netsim import api,data
from netsim.augment import devices

_config_name = 'vxlan.l2tunnel'
_requires    = [ 'vxlan', 'vlan' ]

def pre_link_transform(topology: Box) -> None:
  global _config_name
  # Error if vxlan module is not loaded
  if 'vxlan' not in topology.module:
    log.error(
      'vxlan module is not loaded.',
      log.IncorrectValue,
      _config_name)

'''
post_transform hook

Apply plugin config to nodes running gateway.vrrp for devices that support this plugin
'''
def post_transform(topology: Box) -> None:
  global _config_name
  for node in topology.nodes.values():
    if 'vxlan' not in node.get('module',[]):         # Skip nodes not running vxlan
      continue

    features = devices.get_device_features(node,topology.defaults)
    if 'vxlan.l2tunnel' in features:
      api.node_config(node,_config_name)               # Remember that we have to do extra configuration
    else:
      log.error( f'node {node.name} does not support the vxlan.l2tunnel plugin.',
        log.IncorrectValue,
        _config_name)
