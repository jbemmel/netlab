"""exergy-lab consumes the standard netlab BFD data model unchanged."""

from pathlib import Path

from test_transformation import run_test


def test_exergy_bfd_export() -> None:
  path = Path(__file__).parent / 'integration/exergy-lab/bfd.yml'
  topology = run_test(str(path))
  twin = topology.nodes.twin
  assert twin.bfd.min_tx == 100
  assert twin.bfd.min_rx == 150
  assert twin.bfd.multiplier == 3
  assert twin.bfd.min_echo_rx == 0
  assert 'profiles' not in twin.bfd
  assert twin.bgp.neighbors[0].bfd is True
  assert twin.ospf.bfd is True
  assert twin.isis.bfd == {'ipv4': True, 'ipv6': True}
  assert twin.interfaces[0].ospf.bfd is True
  assert twin.interfaces[0].isis.bfd == {'ipv4': True, 'ipv6': True}
  for proto in ('ospf','isis'):
    assert 'bfd' not in twin.interfaces[1][proto]
  assert twin.interfaces[1].bfd is False
  assert twin.interfaces[2].bfd.min_tx == 200
  assert twin.interfaces[2].bfd.min_rx == 250
  assert topology.nodes.native.bfd.min_tx == twin.bfd.min_tx
  assert topology.nodes.native.bgp.neighbors[0].bfd is True


def test_exergy_llgr_export() -> None:
  path = Path(__file__).parent / 'integration/exergy-lab/llgr.yml'
  topology = run_test(str(path))
  dut = topology.nodes.dut
  assert dut.bgp.gr.state == 'enable'
  assert dut.bgp.gr.restart_time == 13
  assert dut.bgp.gr.notification is True
  assert dut.bgp.llgr.state == 'enable'
  assert dut.bgp.llgr.stale_time == 43
  assert 'llgr' not in dut.bgp.neighbors[0]
  assert dut.bgp.neighbors[1].llgr == 'disable'
  assert dut.vrfs.tenant.bgp.gr.state == 'helper'
  assert dut.vrfs.tenant.bgp.llgr.state == 'helper'
  assert 'stale_time' not in dut.vrfs.tenant.bgp.llgr
