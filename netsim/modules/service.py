#
# Service transformation module
#

from box import Box, BoxList

from . import _Module
from ..utils import log
from ..data.validate import must_be_string, validate_attributes
import warnings

EXTRA_ATTS = {
    "service.name": "str", 
    "service.sap-id": "int",
    "service.spoke-sdp": "int",
}


class SERVICE(_Module):
    def _validate_svc_type(
        self, svc: str, svc_data: Box, topology: Box, node: Box = None
    ):
        if "type" not in svc_data:
            log.error(
                f'Must specify a "type" for service {svc} {f"on node {node.name}" if node else ""}',
                log.MissingValue,
                "service",
            )
            return False
        must_be_string(
            parent=svc_data,
            key="type",
            path=f"services.{svc}",
            module="service",
            valid_values=topology.defaults.service.type.valid_values,
        )
        validate_attributes(
            svc_data,
            topology,
            data_path=f"services.{svc}",
            data_name="service",
            attr_list=["service"],
            # attributes=topology.default.service,
            modules=node.get("module", []) if node else topology.get("module", []),
        )

    def module_pre_transform(self, topology: Box) -> None:
        # Validate service types globally and per node
        if "services" in topology:
            for s, data in topology.services.items():
                self._validate_svc_type(s, data, topology)

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
            for s, data in node.services.items():
                self._validate_svc_type(s, data, topology, node)

    def node_post_transform(self, node: Box, topology: Box) -> None:
        print("JvB service node_post_transform")

        def lookup_service(s):
            if "services" in node and s in node.services:
                return node.services[s]
            elif "services" in topology and s in topology.services:
                return topology.services[s]
            return None

        def resolve_refs(link):
            if "service" in link:
                svcs = []
                for s, d in list(link.service.items()):
                    svc = lookup_service(s)
                    print(f"Found service: {s}->{svc} d={d}")
                    new_svc = svc + (d or {}) + { 'name': s }

                    # Validate attributes
                    validate_attributes(
                        new_svc,
                        topology,
                        data_path=f"link.service.{s}",
                        data_name="service",
                        attr_list=["service","service_interface"],
                        # attributes=topology.default.service,
                        extra_attributes=EXTRA_ATTS,
                        modules=node.get("module", []),
                    )
                    svcs.append( new_svc )
                
                # Reformat 'service' as list with 'name', more convenient for scripts
                link.service = svcs

        # print( f"JvB: Check {node.interfaces}" )
        for link in node.get("interfaces", []):
            print(f"JvB service node_post_transform check {link}")
            resolve_refs(link)

            for n in link.get("neighbors", []):
                resolve_refs(n)

        # Cleanup topology.links
        for link in topology.links:
            for i in link.get("interfaces", []):
                if "service" in i:
                    i.pop("service", None)
            if "service" in link:
                link.pop("service", None)

        print(f"POST: {topology.links}")
