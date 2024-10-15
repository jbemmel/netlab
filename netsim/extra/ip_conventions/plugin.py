from box import Box

"""
Enable 'ip_conventions.primary' attribute per node
"""
def init(topology: Box) -> None:
  topology.defaults.attributes.node.ip_conventions.primary = { 'type': 'bool' }
  topology.defaults.vlan.attributes['global'].ip_conventions = { 'type': 'bool' }
  topology.defaults.attributes['vlan'].ip_conventions = { 'type': 'bool' }
  topology.defaults.vlan.attributes['node'].ip_conventions = { 'type': 'bool' }
  # topology.defaults.vlan.no_propagate.append( 'ip_conventions' )

"""
Apply IP addressing conventions to all nodes and VLANs for which they are enabled
Runs after VLAN IDs and prefixes are assigned
"""
def pre_node_transform(topology: Box) -> None:

  # Apply to any VLAN
  if 'vlans' in topology:
    for v, vlan in topology.vlans.items():
      print(f"JvB: vlan={vlan}")
      if 'ip_conventions' in vlan or 'vlan.ip_conventions' in topology:
        if 'prefix' not in vlan or 'ipv4' not in vlan.prefix or '_auto_assigned' in vlan.prefix:
          vlan.prefix.ipv4 = f"10.2.{vlan.get('id') % 256}.0/24"
        if 'gateway' not in vlan or (vlan.gateway and 'id' not in vlan.gateway):
          vlan.gateway.id = 1
        if 'vrrp' not in vlan.gateway or 'group' not in vlan.gateway.vrrp:
          vlan.gateway.vrrp.group = vlan.id % 256 + 1
        print(f"JvB: post vlan={vlan}")

  # Iterate over nodes with ip_conventions enabled
  for n, ndata in topology.nodes.items():
    if 'ip_conventions' in ndata:
      _primary = ndata.ip_conventions
      for i in ndata.interfaces:
        print( f"JvB: post_transform {i}")
        if i.type=='svi':
          if 'ipv4' not in i:
            i.ipv4 = 2 if _primary else 3
          
