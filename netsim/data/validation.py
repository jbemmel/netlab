#
# Generic topology validation/normalization using Schema
#
import typing, yaml
from box import Box

from schema import Schema, And, Or, Use, Optional

vlan_schema = Schema(
  {
   Optional('id'): And(Use(int), lambda n: 2 <= n <= 4094),
   Optional('evpn'): Schema(
   {
    Optional('vni'): And(Use(int), lambda n: 2 <= n <= 16777215),
    Optional(str): object # Ignore any other key/value pairs
   }
   ),
   Optional(str): object # Ignore any other key/value pairs
  }
)

vlans_schema = Schema(
  {
    Optional(str): Or(Optional(None,default={}),vlan_schema), # name
  }
)

bgp_schema = Schema(
  {
   Optional('as'): And(Use(int), lambda n: 1 <= n <= 65535),
  }
)

node_schema = Schema(
  {
   Optional('id'): int,
   Optional('bgp'): bgp_schema,
   Optional('vlans'): vlans_schema,  # default={}
   Optional('module'): [str],
   Optional(str): object # Ignore any other key/value pairs
  }
)

nodes_schema = Schema(
  {
    str: Or(Optional(None,default={}),node_schema), # name
  }
)

links_schema = Schema(
  {
    str: Or(Optional(None,default={}),dict), # node1 - TODO check referential integrity
    str: Or(Optional(None,default={}),dict), # node2
  }
)

topology_schema = Schema(
  {
   Optional('nodes',default={}): nodes_schema,
   Optional('links',default={}): [ links_schema ],
   Optional('vlans',default={}): vlans_schema,       # default={}

   Optional(str): object # Ignore any other key/value pairs
  }
)

def validate( topology: Box ) -> Box:
  print( "JvB: validation.validate" )
  # return topology
  key = 'nodes'
  print( f"JvB: before nodes {yaml.dump(topology.to_dict())}" )
  result = topology_schema.validate(topology.to_dict())
  print( f"JvB: result nodes {yaml.dump(result)}" )
  reply = Box(result,default_box=True,default_box_none_transform=False,box_dots=False)
  print( f"JvB: Box result   {reply[key]}" )
  return reply
