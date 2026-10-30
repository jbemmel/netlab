# exergy-lab Browser Twin

Use `device: exergy-lab` with the Containerlab provider to run a lab.net relay.
The browser owns the control plane; keep its page open while running the lab.
The initial integration supports numbered BGP, OSPF, and IS-IS configurations,
including those protocols inside VRFs, and VLAN access, trunk, and routed
subinterface topologies, including VXLAN. lab.net reads each VRF from
`/config/exergy-lab.json`, creates the Linux VRF device, and moves its
interfaces into that device. It also creates 802.1Q VLAN devices, per-VLAN
bridges, and VXLAN VTEPs from that file. Advanced protocol options outside that set are
not advertised as supported.

The default image is `ghcr.io/exergy-connect/lab.net-router:latest`, matching the
lab.net deployment default. Override `box` to use another compatible image.

```yaml
provider: clab
module: [ bgp ]
nodes:
  twin:
    device: exergy-lab
    bgp.as: 65001
  native:
    device: frr
    bgp.as: 65002
links:
- twin-native
```

Open `http://<twin-management-ip>:8080/` and launch the browser control plane.
HTTPS is disabled by default. Set `exergy-lab.https: true` to enable it with a
generated TLS certificate. The management address must be
reachable from your browser. Containerlab does not publish this port on the host.

The device runs as root so its protocol agents can use raw sockets and install
routes. Netlab mounts the generated topology at `/config/exergy-lab.json`.
The supervisor loads that file once at startup and waits in `--wait-init` mode.
Containerlab invokes `exergy-lab.net-go --startup` from its exec list after attaching data links.
The supervisor then provisions Linux interfaces and starts the runtime from the
loaded configuration. Runtime reloads do not reread the file or provision Linux.

LLDP is enabled by default (`netlab_lldp_enable: True`). The device sets
`LAB_NET_LLDP=1`, and compatible images run `exergy-lab.net-lldp` on data
interfaces once Containerlab has attached them. The advertised system name is the netlab node
name. Management and loopback interfaces are excluded. Show neighbors with
`exergy-lab.net-lldp show`.

Node attributes `exergy-lab.port` (default 8080), `exergy-lab.https` (default false), and
`exergy-lab.token` configure the relay. The default token is
`lab-net-browser-connect`; set a private token for shared environments.
Generated files contain the token and should be treated as lab credentials.

See `tests/integration/exergy-lab/topology.yml` for a two-router example.
