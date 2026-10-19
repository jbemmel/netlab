"""Validate explicit local SID transformation and Linux configuration generation."""

import ipaddress
import pathlib
import subprocess
import sys

import jinja2
import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]


def transform(tmp_path: pathlib.Path, sid: dict, device: str = 'frr', locator: bool = True) -> tuple:
  node = {'device': device, 'srv6': {'local_sids': {'advance': sid}}}
  if locator:
    node['srv6']['locator'] = '5f00:0:100::/48'
  topology = {
    'provider': 'clab',
    'module': ['routing', 'srv6'],
    'srv6': {'igp': [], 'bgp': False, 'vpn': False},
    'addressing': {'loopback': {'ipv6': '2001:db8::/48'}},
    'nodes': {'r1': node}}
  source = tmp_path / 'topology.yml'
  output = tmp_path / 'result.yml'
  source.write_text(yaml.safe_dump(topology))
  result = subprocess.run(
    [sys.executable, str(ROOT / 'netlab'), 'create', str(source), '-o', f'yaml={output}'],
    cwd=tmp_path, capture_output=True, text=True, check=False)
  return result, yaml.safe_load(output.read_text()) if output.exists() else None


@pytest.mark.parametrize('locator', [True, False])
def test_local_sid_defaults(tmp_path: pathlib.Path, locator: bool) -> None:
  result, topology = transform(tmp_path, {'behavior': 'End', 'flavors': ['next-csid']}, locator=locator)
  assert result.returncode == 0, result.stdout + result.stderr
  node = topology['nodes']['r1']
  assert node['srv6']['local_sids']['advance'] == {
    'prefix': node['srv6']['locator'], 'behavior': 'End', 'flavors': ['next-csid'],
    'block_length': 32, 'csid_length': 16}


def test_local_sid_explicit_prefix(tmp_path: pathlib.Path) -> None:
  result, topology = transform(tmp_path, {'prefix': '5f00:0:100:1::/64', 'behavior': 'End'})
  assert result.returncode == 0, result.stdout + result.stderr
  assert topology['nodes']['r1']['srv6']['local_sids']['advance'] == {
    'prefix': '5f00:0:100:1::/64', 'behavior': 'End', 'flavors': []}


@pytest.mark.parametrize(('sid', 'error'), [
  ({'behavior': 'End', 'prefix': '5f00:0:101::/48'}, 'must be within locator'),
  ({'behavior': 'End', 'flavors': ['next-csid'], 'block_length': 33}, 'multiples of 8'),
  ({'behavior': 'End', 'flavors': ['next-csid'], 'csid_length': 15}, 'multiples of 8'),
  ({'behavior': 'End', 'flavors': ['next-csid'], 'block_length': 112}, 'must be less than 128'),
  ({'behavior': 'End', 'flavors': ['next-csid'], 'block_length': 40}, 'must cover the block'),
  ({'behavior': 'End', 'block_length': 32}, 'require the next-csid'),
  ({'behavior': 'End', 'flavors': ['psp', 'psp']}, 'duplicate flavors'),
  ({'behavior': 'End', 'flavors': ['usp']}, 'does not support usp'),
  ({'behavior': 'End', 'flavors': ['usd']}, 'does not support usd'),
  ({'behavior': 'End', 'flavors': ['replace-csid']}, 'does not support replace-csid'),
  ({'behavior': 'End', 'flavors': ['next-only-csid']}, 'does not support next-only-csid'),
  ({'behavior': 'End.X'}, 'does not support local SID behavior End.X'),
  ({'behavior': 'End.DT6'}, 'does not support local SID behavior End.DT6'),
  ({'behavior': 'Invalid'}, 'valid values'),
  ({'behavior': 'End', 'flavors': ['invalid']}, 'valid values'),
  ({'flavors': ['next-csid']}, 'behavior'),
  ({'behavior': 'End', 'flavors': ['next-csid'], 'block_length': 0}, 'block_length'),
])
def test_invalid_local_sid(tmp_path: pathlib.Path, sid: dict, error: str) -> None:
  result, _ = transform(tmp_path, sid)
  assert result.returncode != 0
  assert error in result.stdout + result.stderr


def test_unsupported_device(tmp_path: pathlib.Path) -> None:
  result, _ = transform(tmp_path, {'behavior': 'End'}, device='eos')
  assert result.returncode != 0
  assert 'does not support local SID behavior End' in result.stdout + result.stderr


@pytest.mark.parametrize('flavors', [[], ['psp'], ['next-csid'], ['psp', 'next-csid']])
def test_linux_local_sid_commands(tmp_path: pathlib.Path, flavors: list) -> None:
  result, topology = transform(tmp_path, {'behavior': 'End', 'flavors': flavors})
  assert result.returncode == 0, result.stdout + result.stderr
  env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(ROOT / 'netsim/ansible/templates/srv6'),
    undefined=jinja2.ChainableUndefined, trim_blocks=True)
  env.filters['ansible.utils.ipaddr'] = lambda value, _: str(ipaddress.ip_interface(value).ip)
  node = topology['nodes']['r1']
  rendered = env.get_template('frr.j2').render(**node, inventory_hostname='r1')
  expected = 'ip -6 route replace 5f00:0:100::/48 encap seg6local action End'
  if flavors:
    expected += ' flavors ' + ','.join(flavors)
  if 'next-csid' in flavors:
    expected += ' lblen 32 nflen 16'
  expected += ' dev ${SRv6_DEV}'
  assert expected in rendered.splitlines()
  syntax = subprocess.run(['bash', '-n'], input=rendered, text=True, capture_output=True, check=False)
  assert syntax.returncode == 0, syntax.stderr


def test_duplicate_prefix(tmp_path: pathlib.Path) -> None:
  result, topology = transform(tmp_path, {'behavior': 'End'})
  assert result.returncode == 0, result.stdout + result.stderr
  source = tmp_path / 'topology.yml'
  config = yaml.safe_load(source.read_text())
  config['nodes']['r1']['srv6']['local_sids']['second'] = {
    'behavior': 'End', 'prefix': '5f00:0:100::/48'}
  source.write_text(yaml.safe_dump(config))
  result = subprocess.run(
    [sys.executable, str(ROOT / 'netlab'), 'create', str(source), '-o', f'yaml={tmp_path / "duplicate.yml"}'],
    cwd=tmp_path, capture_output=True, text=True, check=False)
  assert result.returncode != 0
  assert 'duplicates local SID prefix' in result.stdout + result.stderr
