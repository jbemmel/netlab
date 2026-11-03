# exergy-lab Browser Twin

Use `device: exergy-lab` with the Containerlab provider to run a lab.net relay.
Compatible images start an embedded headless browser controller automatically.
An interactive browser can also own the control plane.

The device supports these features through the Go/Linux dataplane:

* IPv4 and IPv6 BGP, IPv6 link-local transport, IPv4 over IPv6 transport
  (RFC 8950), local AS (including IBGP and VRFs), confederations, address-family
  activation, prefix advertisement, and configurable keepalive/hold timers.
* OSPFv2, OSPFv3, and IS-IS, including routing inside VRFs.
* Asynchronous BFD for BGP, OSPFv2, OSPFv3, and IS-IS over IPv4 or IPv6.
* VLAN access, trunks, routed subinterfaces, and static VXLAN with IPv4 or IPv6 VTEPs.
* VXLAN EVPN bridging and symmetric IRB with tenant L3 VNIs, multiple import/export
  route targets, and IPv4/IPv6 tenant reachability.
* LAG interfaces using Linux bonds, including active and passive LACP and EVPN Ethernet Segments.
* IPv4 and IPv6 anycast gateways on routed interfaces and SVIs, including VRFs.
* The existing BGP SRv6 IPv4 service signaling over IPv6 transport.

Netlab mounts the resolved topology at `/config/exergy-lab.json`. The runtime
creates Linux VRFs, VLAN devices, bridges, bonds, VXLAN VTEPs, and anycast gateway
interfaces from that file. Module configuration does not require a separate CLI. The device belongs to the
`unprovisioned` group so netlab skips dynamic provisioning; Containerlab mounts
the JSON config template and invokes the runtime startup hook.

Native VRRP, asymmetric EVPN IRB, and EVPN MPLS transport are not advertised.
The `evpn.multihoming` plugin's segment id is the Ethernet Segment Identifier.

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

## BFD

Add the `bfd` module and enable BFD on routing protocols or BGP sessions:

```yaml
provider: clab
module: [ bgp, ospf, bfd ]
plugin: [ bgp.session ]
bfd:
  min_tx: 100
  min_rx: 100
  multiplier: 3
ospf.bfd: true
nodes:
  twin:
    device: exergy-lab
    bgp.as: 65001
  native:
    device: frr
    bgp.as: 65002
links:
- twin:
  native:
  role: internal
  bgp.bfd: true
```

`role: internal` keeps the IGP enabled on this inter-AS link. Use `isis.bfd: true`
for IS-IS. Per-interface BFD timers override node timers; `bfd: false` disables
IGP BFD on an interface. The `bgp.session` plugin supplies BGP neighbor enablement.
The device consumes the standard resolved netlab BFD settings directly from the
mounted JSON, including protocol enablement and node/interface timers.

Intervals are milliseconds (1–60000), and the detection multiplier is 1–255.
Use a current lab.net image containing the BFD helper and browser runtime.
Echo mode, authentication, demand mode, and strict BFD are unsupported. IS-IS
honors the per-address-family BFD flags on dual-stack interfaces.

See `tests/integration/exergy-lab/bfd.yml` for a dual-stack FRR interoperability
lab with shared protocol sessions, interface opt-outs, and timer overrides.
Inspect BFD in the browser's BFD tab and use `show bfd peers` on FRR.

## BGP Graceful Restart

The `bgp.session` plugin's `bgp.gr` settings are supported at node, VRF, and
neighbor level. The device consumes the resolved JSON directly, including
`state` (`enable`, `helper`, or `disable`), `restart_time`, and `stalepath_time`.
VRFs have independent settings; node-level GR settings do not propagate to them.
GR is disabled unless explicitly configured. IPv4 unicast, IPv6 unicast, and
EVPN use independent negotiated restart state and End-of-RIB processing.

Use a current lab.net image or update its browser/WASM artifacts before testing.
`tests/integration/bgp.session/14-gr.yml` checks the advertised restart, helper,
and disabled modes against FRR probes, including VRF neighbors. Run it from an
empty deployment directory with `netlab up -d exergy-lab -p clab <path-to-test>`,
then run `netlab validate` after any local artifact update.

Lab.net also supports opt-in LLGR through the `bgp.session` plugin's `bgp.llgr`
settings, using a `state` and a `stale_time` in seconds. LLGR requires GR
to be enabled or in helper mode on the same session. RFC 8538 is enabled with GR by default: the device advertises the N bit and
retains routes after eligible notifications and hold-timer expiry when both
peers negotiate it. Set `bgp.gr.notification: false` to use legacy notification
handling. Cease/Hard Reset always removes routes, as do administrative node/link
and BFD failures. Explicit withdrawals are never deferred.
