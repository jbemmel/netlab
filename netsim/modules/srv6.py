#
# SRv6 transformation module
#
from box import Box

from . import _Module
from ..utils import log
import netaddr

class SRV6(_Module):

  def node_post_transform(self, node: Box, topology: Box) -> None:

      if 'ipv6' not in node.loopback:
        log.error( f"SRv6 requires an ipv6 loopback address on node {node.name}",
                   log.MissingValue, 'srv6' )

      # Could model this as another addressing pool too
      if topology.defaults.srv6.locator:
        locator = netaddr.IPNetwork( f'{topology.defaults.srv6.locator}:{node.id:x}::/64' )

        if netaddr.IPNetwork(node.loopback.ipv6) in locator:
          log.error( f"Node {node.name} ipv6 loopback address {node.loopback.ipv6} overlaps with locator {locator}",
                        log.IncorrectValue, 'srv6' )

        node.srv6.locator = str( locator )

      if topology.defaults.srv6.micro_locator:
        locator = netaddr.IPNetwork( f'{topology.defaults.srv6.micro_locator}:{node.id:x}::/32' )

        if netaddr.IPNetwork(node.loopback.ipv6) in locator:
          log.error( f"Node {node.name} ipv6 loopback address {node.loopback.ipv6} overlaps with micro_locator {locator}",
                        log.IncorrectValue, 'srv6' )

        node.srv6.micro_locator = str( locator )

      if not ('locator' in node.srv6 or 'micro_locator' in node.srv6):
        log.error( f"SRv6 requires at least one of srv6.locator or srv6.micro_locator for node {node.name}",
                   log.MissingValue, 'srv6' )

      # TODO process per-interface srv6 parameters?
      # for l in node.get('interfaces',[]):
