#
# Service transformation module
#
import netaddr
from box import Box

from . import _Module
from ..augment import devices
from ..utils import log
from ..data.validate import must_be_string, validate_attributes
import warnings

EXTRA_ATTS = {
    "service.name": "str",
    "service.sap-id": {"type": "int", "_alt_types": "str"},
    "service.spoke-sdp": "int",
}


class SERVICE(_Module):
    def _validate_svc_type(
        self, svc: str, svc_data: Box, topology: Box, node: Box, features: Box
    ):
        if "type" not in svc_data:
            log.error(
                f'Must specify a "type" for service {svc} on node {node.name}',
                log.MissingValue,
                "service",
            )
            return False
        must_be_string(
            parent=svc_data,
            key="type",
            path=f"services.{svc}",
            module="service",
            valid_values=features.service.attributes["global"].type.valid_values 
            # topology.defaults.service.attributes["global"].type.valid_values,
        )
        # Duplicate, happens at node interface resolution
        # validate_attributes(
        #     svc_data,
        #     topology,
        #     data_path=f"services.{svc}",
        #     data_name="service",
        #     attr_list=["service"],
        #     attributes=features.service.attributes,
        #     modules=node.get("module", []),
        # )

    def module_pre_transform(self, topology: Box) -> None:
        # Validate service types ONLY per node
        # if "services" in topology:
        #     for s, data in topology.services.items():
        #         self._validate_svc_type(s, data, topology)

        # Promote link-level service attributes to all interfaces on that link
        for link in topology.links:
            if "service" in link:
                for intf in link.get("interfaces", []):
                    if "service" not in intf:
                        print(f"JvB promoted link service to interface {intf}")
                        intf.service = link.service
                    else:
                        warnings.warn(
                            "Interface level 'service' may override link level attributes"
                        )
                        intf.service = link.service + intf.service
                link.pop("service", None)

    def node_pre_transform(self, node: Box, topology: Box) -> None:
        print("JvB service node_post_transform")

        if "services" in node:
            features = devices.get_device_features(node,topology.defaults)
            if 'service' not in features:
                log.error(
                f'Node {node.name} does not support "service" module',
                log.IncorrectAttr,
                "service",
                )
                return False
            for s, data in node.services.items():
                self._validate_svc_type(s, data, topology, node, features)

    def node_post_transform(self, node: Box, topology: Box) -> None:
        print("JvB service node_post_transform")
        features = devices.get_device_features(node,topology.defaults)
        def lookup_service(s):
            if "services" in node and s in node.services:
                return node.services[s]
            elif "services" in topology and s in topology.services:
                return topology.services[s]
            return None

        def resolve_refs(intf, resolve_sap_id=False):
            if "service" in intf:
                svcs = []
                sap_resolved = False
                for s, d in list(intf.service.items()):
                    svc = lookup_service(s)
                    print(f"Found service: {s}->{svc} d={d}")
                    new_svc = svc + (d or {}) + {"name": s}

                    # Validate attributes, this includes service type
                    validate_attributes(
                        new_svc,
                        topology,
                        data_path=f"interface.service.{s}",
                        data_name="service",
                        attr_list=["service", "service_interface"],
                        attributes=features.service.attributes,
                        extra_attributes=EXTRA_ATTS,
                        modules=node.get("module", []),
                    )

                    # Resolve any sap-id to VLANs if requested
                    if (
                        resolve_sap_id
                        and "sap-id" in new_svc
                        and new_svc["sap-id"] == "vlan"
                    ):
                        if "vlan" not in intf:
                            log.error(
                                f"sap-id vlan resolution requested but no vlan on link {intf} node {node.name}",
                                log.MissingValue,
                                "service",
                            )
                            return False
                        elif "access_id" in intf.vlan:
                            new_svc["sap-id"] = None  # access vlan -> untagged
                            sap_resolved = True
                        elif "trunk" in intf.vlan:  # TODO
                            log.error(
                                f"sap-id vlan resolution for trunk on {intf} node {node.name} not supported yet",
                                log.IncorrectAttr,
                                "service",
                            )
                            return False

                    svcs.append(new_svc)

                # Reformat 'service' as list with 'name', more convenient for scripts
                intf.service = svcs

                # Check if any SAPs were resolved, if so remove any VLAN
                if sap_resolved:
                    intf.pop("vlan", None)  # TODO remove SVI too
                return True

            return False  # no 'service' on interface

        # print( f"JvB: Check {node.interfaces}" )
        for intf in node.get("interfaces", []):
            print(f"JvB service node_post_transform check {intf}")

            # Only resolve neighbors if a service is present
            if resolve_refs(intf, resolve_sap_id=True):
                for n in intf.get("neighbors", []):
                    resolve_refs(n)

                    # Add system IP, some services need this
                    nb = topology.nodes[n.node]
                    if "loopback" in nb and "ipv4" in nb.loopback:
                        n.system_ip = str(netaddr.IPNetwork(nb.loopback.ipv4).ip)

        # Cleanup topology.links
        for link in topology.links:
            for i in link.get("interfaces", []):
                if "service" in i:
                    i.pop("service", None)
            if "service" in link:
                link.pop("service", None)

        print(f"POST: {topology.links}")
