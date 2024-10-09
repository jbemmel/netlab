import typing
import netaddr
import re

from box import Box, BoxList
from . import _Module
from .. import data
from ..utils import log
from ..augment import devices, links

GROUPNAME = re.compile(r'^links\[(?P<group>\w+)\]\[\d+\]')

class LAG(_Module):

  """
  link_pre_transform: Process LAG links and add member links to the topology
  """
  def link_pre_transform(self, link: Box, topology: Box) -> None:
    if log.debug_active('lag'):
      print(f'LAG link_pre_transform for {link}')

    # Iterate over links with type lag, created for link group(s)
    if link.get('type',"")=="lag" and not ('lag' in link and '_parent' in link.lag):
      if not GROUPNAME.match(link._linkname):
         log.error(
              f'LAG link {link._linkname} is not part of a link group',
              category=log.IncorrectAttr,
              module='lag',
              hint='lag')

      if len(link.interfaces)!=2: # Future: MC-LAG would be 3
        log.error(
            'Current LAG module only supports lags between exactly 2 nodes',
            category=log.IncorrectAttr,
            module='lag',
            hint='lag')

      # 1. Check that the nodes involved all support LAG
      for i in link.interfaces:
        n = topology.nodes[i.node]
        features = devices.get_device_features(n,topology.defaults)
        if 'lag' not in features:
          log.error(
              f'Node {n.name} does not support LAG configured on link {link._linkname}',
              category=log.IncorrectAttr,
              module='lag',
              hint='lag')
        ATT = 'lag.lacp_mode'
        lacp_mode = i.get(ATT) or link.get(ATT) or n.get(ATT) or topology.defaults.get(ATT)
        if lacp_mode=='passive' and not features.lag.get('passive',False):
          log.error(
              f'Node {n.name} does not support passive LACP configured on link {link._linkname}',
              category=log.IncorrectAttr,
              module='lag',
              hint='lag')

      group_name = GROUPNAME.search(link._linkname).group("group")
       
      # Find parent virtual link, create if not existing
      parent = [ l for l in topology.links if l.get("type")=="lag" and l._linkname == group_name ]
      if not parent:
        parent = data.get_box(link)
        parent._linkname = group_name
        parent.linkindex = len(topology.links) + 1
        parent.interfaces = link.interfaces + []    # Deep copy
        parent.lag._parent = True                   # Set flag for filtering
        topology.links.append( parent )
        if log.debug_active('lag'):
          print(f'LAG link_pre_transform created virtual parent {parent}')
      else:
        parent = parent[0]
        # parent.interfaces.extend( link.interfaces )  # results in duplicate bond interfaces?

      # Modify the LAG member link
      link.type = "p2p"                   # Change type back to p2p
      link.lag = link.lag or {}           # ..and make sure template code can check for lag links
      link.prefix = False                 # Disallow IP addressing
      link.pop('vlan',None)               # Remove any VLAN, moved to the virtual lag interface
      link.parentindex = parent.linkindex # Link physical interface to its virtual parent

      if log.debug_active('lag'):
        print(f'After LAG link_pre_transform: {link}')
