#
# Clabernetes provider module
#
import typing
import json
import os
import subprocess
from box import Box

from ..utils import log
from ..data import get_empty_box
from ..cli import external_commands
from ..augment import devices
from .clab import Containerlab

class Clabernetes(Containerlab):

  #
  # Pretend to be mostly the same provider as 'clab'
  #
  def __init__(self, provider: str, data: Box) -> None:
    super().__init__('clab',data)

  def node_set_image(self, node: Box, topology: Box) -> None:
    print(f"clabernetes node_set_image {node.name}")
    clab_data = topology.defaults.devices[node.device].get('clab',{})
    if clab_data:
      print(f"clab data: {clab_data}")
      if 'image' in clab_data:
        node.box = clab_data.image
      if 'clab' not in node:
        node.clab = clab_data.node
      else:
        node.clab = clab_data.node + node.clab

  #
  # Use the 'clab' template base
  #
  def get_template_path(self) -> str:
    return 'templates/provider/clab'

  #
  # Generate Clabernetes manifests after creating Clab topology
  #
  def create(self, topology: Box, fname: typing.Optional[str]) -> None:
    super().create(topology,fname)

    # generate manifests
    try:
      status = external_commands.run_command(
                  f'sudo docker run --user {os.getuid()} \
                   -v {os.getcwd()}:/clabernetes/work --rm \
                   ghcr.io/srl-labs/clabernetes/clabverter \
                   --naming non-prefixed --topologyFile clab.yml --outputDirectory clabernetes_files',
                  run_always=True)
    except:
      log.error('Error running "clabverter": {ex}',category=log.FatalError,module='clabernetes')

  def pre_start_lab(self, topology: Box) -> None:
    log.print_verbose('pre-start hook for Clabernetes - create load balancer')

    # create load balancer for mgmt network
    try:
      rbac_status = external_commands.run_command("kubectl apply -f https://kube-vip.io/manifests/rbac.yaml")
      kv_status = external_commands.run_command("kubectl apply -f https://raw.githubusercontent.com/kube-vip/kube-vip-cloud-provider/main/manifest/kube-vip-cloud-controller.yaml")
      cfg_status = external_commands.run_command("kubectl create configmap --namespace kube-system kubevip --from-literal range-global=172.18.1.10-172.18.1.250")
    
      cmd = "docker run --network host --rm ghcr.io/kube-vip/kube-vip:v0.8.0 \
             manifest daemonset --services --inCluster --arp --interface eth0"
      # manifest = external_commands.run_command("docker run --network host --rm ghcr.io/kube-vip/kube-vip:v0.8.0 \
      #                                           manifest daemonset --services --inCluster --arp --interface eth0", return_stdout=True)
      
      ps = subprocess.Popen([ arg for arg in cmd.split(" ") ], stdout=subprocess.PIPE)
      output = subprocess.check_output(('kubectl','apply','-f','-'), stdin=ps.stdout)
      ps.wait()
      log.print_verbose( f"Result: {output}" )

      # TODO update ansible_host for each node with assigned IP

    except:
      log.error('Error creating kube-vip load balancer: {ex}',category=log.FatalError,module='clabernetes')

  def post_stop_lab(self, topology: Box) -> None:
    log.print_verbose('post-stop hook for Clabernetes, do nothing')

    try:
      cfg_status = external_commands.run_command("kubectl delete configmap --namespace kube-system kubevip")
      kv_status = external_commands.run_command("kubectl delete -f https://raw.githubusercontent.com/kube-vip/kube-vip-cloud-provider/main/manifest/kube-vip-cloud-controller.yaml")
      rbac_status = external_commands.run_command("kubectl delete -f https://kube-vip.io/manifests/rbac.yaml")
    
    except:
      log.error('Error creating kube-vip load balancer: {ex}',category=log.FatalError,module='clabernetes')

  def get_lab_status(self) -> Box:
    try:
      status = external_commands.run_command(
                  'kubectl get -n c9s pods -o json',
                  check_result=True,
                  ignore_errors=True,
                  return_stdout=True,
                  run_always=True)
      
      stat_box = get_empty_box()
      if not isinstance(status,str):
        return stat_box
      try:
        for line in status.split('\n'):
          if not line.startswith('{'):
            continue
          docker_stats = json.loads(line)
          # stat_box[docker_stats['Names']].status = docker_stats['Status']
          # stat_box[docker_stats['Names']].image = docker_stats['Image']
      except Exception as ex:
        log.error(f'Cannot get kubectl status: {ex}',category=log.FatalError,module='clabernetes')
        return stat_box

      return stat_box
    except:
      log.error('Cannot execute "kubectl get": {ex}',category=log.FatalError,module='clabernetes')
      return get_empty_box()

  # def get_node_name(self, node: str, topology: Box) -> str:
  #   return f'clab-{ topology.name }-{ node }'
