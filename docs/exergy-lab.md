# exergy-lab Browser Twin

Use `device: exergy-lab` with the Containerlab provider to run a lab.net relay.
Compatible images start an embedded headless browser controller automatically.
An interactive browser can also own the control plane.

The device supports these features through the Go/Linux dataplane:

* IPv4 and IPv6 BGP, IPv6 link-local transport, IPv4 over IPv6 transport
  (RFC 8950), local AS (including IBGP and VRFs), confederations, address-family
  activation, prefix advertisement, and configurable keepalive/hold timers.
* OSPFv2, OSPFv3, and IS-IS, including routing inside VRFs.
* VLAN access, trunks, routed subinterfaces, and static VXLAN with IPv4 or IPv6 VTEPs.
* VXLAN EVPN bridging and symmetric IRB with tenant L3 VNIs, multiple import/export
  route targets, and IPv4/IPv6 tenant reachability.
* LAG interfaces using Linux bonds, including active and passive LACP.
* IPv4 and IPv6 anycast gateways on routed interfaces and SVIs, including VRFs.
* The existing BGP SRv6 IPv4 service signaling over IPv6 transport.

Netlab mounts the resolved topology at `/config/exergy-lab.json`. The runtime
creates Linux VRFs, VLAN devices, bridges, bonds, VXLAN VTEPs, and anycast gateway
interfaces from that file. Module configuration does not require a separate CLI. The device belongs to the
`unprovisioned` group so netlab skips dynamic provisioning; Containerlab mounts
the JSON config template and invokes the runtime startup hook.

Native VRRP, asymmetric EVPN IRB, and EVPN MPLS transport are not advertised.
The lab.net runtime also supports EVPN Ethernet Segments, but netlab's
`evpn.multihoming` plugin uses a different ESI representation and is not yet
integrated with this device.

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

Open `http://<twin-management-ip>:4242/?lab=running-lab` to inspect the running lab.
The embedded headless browser owns the control plane by default; additional browser
pages provide read-only inspection of its live state. An interactive browser can
own the control plane when no other controller owns it; keep that page open while
it does.
Set `LAB_NET_HEADLESS=0` in the container environment to disable the embedded controller.
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

Node attributes `exergy-lab.port` (default 4242), `exergy-lab.https` (default false), and
`exergy-lab.token` configure the relay. The default token is
`lab-net-browser-connect`; set a private token for shared environments.
Generated files contain the token and should be treated as lab credentials.

See `tests/integration/exergy-lab/topology.yml` for a two-router example.
