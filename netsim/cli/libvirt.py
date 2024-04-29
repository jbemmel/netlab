#
# netlab config command
#
# Deploy custom configuration template to network devices
#
import typing

from box import Box

from ..utils import log, read as _read
from .libvirt_actions import libvirt_usage,package,config

def run(cli_args: typing.List[str]) -> None:
  topology = _read.system_defaults()
  if not topology:
    log.fatal("Cannot read the system defaults","libvirt")

  if not cli_args:
    libvirt_usage()
    return

  if cli_args[0] == 'package':
    try:
      package.run(cli_args[1:],topology)
    except KeyboardInterrupt as ex:
      print("")
      log.error(
        'Aborted by user. VM and management network might still be running',
        category=log.FatalError,
        module='libvirt')
  elif cli_args[0] == 'config':
    config.run(cli_args[1:],topology.settings)
  else:
    libvirt_usage()
