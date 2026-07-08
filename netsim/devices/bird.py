#
# Bird quirks
#
from box import Box

from ..augment import devices as a_devices
from . import _Quirks
from ._common import check_daemon_dataplane_config


def bird_transform_rt(rt: str) -> str:
  '''
  Transform standard RT notation A:B into BIRD RT notation (rt,A,B)

  Split the original route target into its components, rejoin them
  separated by commas and add (rt,) around them
  '''
  return '(rt,'+','.join(rt.split(':'))+')'

def bird_vrf_rt(node: Box) -> None:
  '''
  Convert standard VRF route targets into (rt,a,b) format used by Bird configuration
  '''
  for vdata in node.get('vrfs',{}).values():                # Iterate over all VRFs
    for kw in ('import','export'):                          # Process import and export RTs
      if kw not in vdata:                                   # Not relevant? Cool ;)
        continue

      vdata[f'_bird_{kw}'] = [ bird_transform_rt(rt) for rt in vdata[kw]]

def bird_vlan_evpn_rt(node: Box) -> None:
  '''
  Convert standard MAC VRF EVPN route targets into (rt,a,b) format used by Bird configuration

  Note: the IP-VRF EVPN RTs are transformed by bird_vrf_rt function
  '''
  for vdata in node.get('vlans',{}).values():               # Iterate over all VLANs
    if 'evpn' not in vdata:                                 # Skip non-EVPN VLANs
      continue
    for kw in ('import','export'):                          # Process import and export RTs
      if kw not in vdata.evpn:                              # Not relevant? Cool ;)
        continue

      vdata.evpn[f'_bird_{kw}'] = [ bird_transform_rt(rt) for rt in vdata.evpn[kw]]

def bird_daemon_includes(node: Box, topology: Box) -> None:
  '''
  Build ordered list of BIRD configuration files to include from bird.conf.

  extra_daemon_config snippets (for example MPLS domain) must be parsed before
  module configuration files that reference them (for example BGP-LU).
  '''
  if not node.get('_daemon',False) or '_daemon_config' not in node:
    return

  features = a_devices.get_device_features(node,topology.defaults)
  extra_cp = features.initial.get('extra_daemon_config',{})
  node_mods = node.get('module',[])
  includes: list[str] = []
  seen: set[str] = set()

  def add_include(path: str) -> None:
    if path.endswith('.sh') or path in seen:
      return
    seen.add(path)
    includes.append(path)

  for mod, path in extra_cp.items():
    if mod not in node_mods:
      continue
    add_include(path)

  for key, path in node._daemon_config.items():
    if key.startswith('_') or key == node.device:
      continue
    add_include(path)

  node._bird_daemon_includes = includes

class Bird(_Quirks):

  @classmethod
  def device_quirks(self, node: Box, topology: Box) -> None:
    check_daemon_dataplane_config(node,topology)
    bird_daemon_includes(node,topology)
    bird_vrf_rt(node)
    bird_vlan_evpn_rt(node)
