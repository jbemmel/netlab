"""Exergy Lab consumes the resolved JSON topology without CLI provisioning."""

from box import Box

from ..data import append_to_list
from . import _Quirks


class ExergyLab(_Quirks):

  @classmethod
  def device_quirks(cls, node: Box, topology: Box) -> None:
    append_to_list(topology.groups.unprovisioned, 'members', node.name)
