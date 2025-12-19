#
# YANG validation plugin - Basic version
#
import json
import re
import traceback
import typing
from pathlib import Path

from box import Box

from netsim.utils import files as _files
from netsim.utils import log


def load_yang_model_path(model_path: str) -> Path:
  """
  Get Path object for YANG model file
  """
  if "package:" in model_path:
    pkg_files = _files.get_traversable_path("package:")
    model_file = pkg_files.joinpath(model_path.replace("package:", ""))
    if not model_file.exists():
      raise FileNotFoundError(f"YANG model not found: {model_path}")
    return model_file
  else:
    model_file = Path(model_path)
    if not model_file.exists():
      raise FileNotFoundError(f"YANG model not found: {model_path}")
    return model_file


def _convert_nodes_to_list(topo_dict: dict) -> None:
  """
  Convert nodes dictionary to list format to match YANG model.
  
  YANG model defines nodes as: list nodes { key "name"; leaf name; container stp; anydata node_data; }
  
  This function converts the nodes dictionary to a list, extracting name and stp container,
  and putting the rest in node_data.
  
  Args:
    topo_dict: Topology dictionary (modified in place)
  """
  if "nodes" not in topo_dict or not isinstance(topo_dict["nodes"], dict):
    return
  
  # Convert nodes dictionary to list format
  node_list = []
  for node_name, node_data in topo_dict["nodes"].items():
    if isinstance(node_data, dict):
      node_entry = {"name": node_name}
      # Extract stp container and put rest in node_data
      if "stp" in node_data:
        node_entry["stp"] = node_data.pop("stp")
      # Put remaining fields in node_data
      if node_data:
        node_entry["node_data"] = dict(node_data)
      node_list.append(node_entry)
    else:
      node_entry = {"name": node_name, "node_data": node_data}
      node_list.append(node_entry)
  topo_dict["nodes"] = node_list


def _convert_links_and_interfaces(topo_dict: dict) -> None:
  """
  Transform link and interface structures to match YANG model.
  
  YANG model defines:
  - Links: leaf linkindex, anydata link_data, list interfaces
  - Interfaces: leaf node, container bgp, container stp, anydata interface_data
  
  This function wraps link fields (except linkindex and interfaces) into link_data,
  and extracts structured interface elements to top level, moving remaining fields into interface_data.
  
  Args:
    topo_dict: Topology dictionary (modified in place)
  """
  if "links" not in topo_dict or not isinstance(topo_dict["links"], list):
    return
  
  for link in topo_dict["links"]:
    if not isinstance(link, dict):
      continue
    
    # Wrap all link fields (except linkindex and interfaces) into link_data
    link_data = {k: link.pop(k) for k in list(link.keys()) if k not in ["linkindex", "interfaces"]}
    if link_data:
      link["link_data"] = link_data
    
    # Transform interfaces within the link
    if "interfaces" in link and isinstance(link["interfaces"], list):
      for intf in link["interfaces"]:
        if isinstance(intf, dict):
          # Extract structured interface elements and put rest in interface_data
          intf_data = {k: intf.pop(k) for k in list(intf.keys()) if k not in ["node", "stp"]}
          if intf_data:
            intf["interface_data"] = intf_data


def topology_to_json(topology: Box, yang_model_path: typing.Optional[str] = None) -> dict:
  """
  Convert topology Box structure to JSON-compatible dictionary for YANG validation

  Args:
    topology: The topology Box structure
    yang_model_path: Optional path to YANG model file to extract namespace from
  """
  # Convert Box to dict and handle special cases
  topo_dict = topology.to_dict()

  # Remove all internal/private keys starting with '_' before YANG validation
  def remove_underscore_keys(obj: typing.Any, depth: int = 0) -> None:
    if depth > 10:  # Prevent infinite recursion
      return
    if isinstance(obj, dict):
      keys_to_remove = []
      for key in obj.keys():
        if key.startswith("_"):
          keys_to_remove.append(key)
        else:
          # Recursively process nested structures
          remove_underscore_keys(obj[key], depth + 1)
      # Remove underscore-prefixed keys
      for key in keys_to_remove:
        del obj[key]
    elif isinstance(obj, list):
      for item in obj:
        remove_underscore_keys(item, depth + 1)

  remove_underscore_keys(topo_dict)

  # Transform nodes dictionary to list format for YANG validation
  _convert_nodes_to_list(topo_dict)
  
  # Transform link and interface structures to match YANG model
  _convert_links_and_interfaces(topo_dict)
  

  # Extract namespace prefix from YANG model if path provided
  namespace_prefix = "netlab-topology"  # Default
  if yang_model_path:
    try:
      model_file = load_yang_model_path(yang_model_path)
      with open(model_file, "r") as f:
        yang_content = f.read()
      # Extract module name (used as namespace prefix)
      mod_match = re.search(r"module\s+(\S+)\s*\{", yang_content)
      if mod_match:
        namespace_prefix = mod_match.group(1)
    except Exception:
      pass  # Use default if extraction fails

  # Wrap in namespace container for YANG validation
  # yangson expects the data under the namespace-qualified container name
  return {f"{namespace_prefix}:topology": topo_dict}


def _create_yang_library(yang_content: str, yang_dir: str) -> str:
  """
  Extract module metadata from YANG content and create YANG library JSON.

  Args:
    yang_content: YANG module content as string
    yang_dir: Directory containing YANG model files

  Returns JSON string in ietf-yang-library format.
  """
  # Extract module name, revision, and namespace from YANG content
  mod_match = re.search(r"module\s+(\S+)\s*\{", yang_content)
  rev_match = re.search(r"revision\s+(\S+)\s*\{", yang_content)
  ns_match = re.search(r'namespace\s+"([^"]+)"', yang_content)

  if not mod_match:
    raise ValueError("Failed to extract module name from YANG file")
  if not rev_match:
    raise ValueError("Failed to extract revision from YANG file")
  if not ns_match:
    raise ValueError("Failed to extract namespace from YANG file")

  mod_name = mod_match.group(1)
  mod_revision = rev_match.group(1)
  mod_namespace = ns_match.group(1)

  modules = [{"name": mod_name, "revision": mod_revision, "namespace": mod_namespace, "conformance-type": "implement"}]

  # Extract imports and include imported modules
  import_pattern = r"import\s+(\S+)\s*\{[^}]*revision-date\s+(\S+);"
  for import_match in re.finditer(import_pattern, yang_content):
    imported_mod = import_match.group(1)
    imported_rev = import_match.group(2)

    # Try to load the imported module to get its namespace
    try:
      import_path = Path(yang_dir) / f"{imported_mod}.yang"
      if import_path.exists():
        with open(import_path, "r") as f:
          imported_content = f.read()
        imported_ns_match = re.search(r'namespace\s+"([^"]+)"', imported_content)
        if imported_ns_match:
          # Check if module is already in the list
          if not any(m["name"] == imported_mod for m in modules):
            modules.append(
              {
                "name": imported_mod,
                "revision": imported_rev,
                "namespace": imported_ns_match.group(1),
                "conformance-type": "implement",
              }
            )
    except Exception:
      pass  # Skip if imported module can't be loaded

  # Create YANG library JSON (ietf-yang-library format)
  yang_library = {"ietf-yang-library:modules-state": {"module-set-id": "netlab-topology-set", "module": modules}}

  return json.dumps(yang_library)


def validate_topology_yang(topology: Box, yang_model_path: str, phase: str) -> typing.List[str]:
  """
  Validate topology against YANG model using actual YANG MUST statements

  Uses yangson library to parse the YANG model and validate the topology data,
  including evaluation of MUST statements.

  Args:
    topology: The topology Box structure
    yang_model_path: Path to the YANG model file
    phase: Phase name for logging (e.g., 'init', 'post_transform')

  Returns list of error messages, empty list if validation passes
  """
  errors: typing.List[str] = []

  # Check if yangson is available
  try:
    from yangson import DataModel  # type: ignore[import-untyped]
    from yangson.enumerations import ContentType, ValidationScope  # type: ignore[import-untyped]
    from yangson.exceptions import (  # type: ignore[import-untyped]
      RawMemberError,
      SchemaError,
      SemanticError,
      YangTypeError,
    )
  except ImportError as ex:
    log.fatal(f"yangson library not found: {ex}. Install it with: pip install yangson", module="yang_validation")
    return errors

  # Load YANG model file
  try:
    yang_model_file = load_yang_model_path(yang_model_path)
  except FileNotFoundError as ex:
    log.fatal(f"YANG model not found: {ex}", module="yang_validation")
    return errors

  # Read YANG model file content
  try:
    with yang_model_file.open("r") as f:
      yang_content = f.read()
  except Exception as ex:
    log.fatal(f"Failed to read YANG model file: {ex}", module="yang_validation")
    return errors

  # Create data model from YANG file
  # yangson requires YANG library JSON format, not raw YANG files
  yang_dir = str(yang_model_file.parent)

  try:
    yang_library_json = _create_yang_library(yang_content, yang_dir)
    dm = DataModel(yang_library_json, [yang_dir])
  except SchemaError as ex:
    log.fatal(f"Failed to load YANG model: {ex}", module="yang_validation")
    return errors
  except ValueError as ex:
    log.fatal(f"Invalid YANG model format: {ex}", module="yang_validation")
    return errors
  except Exception as ex:
    log.fatal(f"Failed to create YANG data model: {ex}", module="yang_validation")
    return errors

  # Convert topology to JSON format and validate
  try:
    topo_json = topology_to_json(topology, yang_model_path)

    if log.debug_active("yang_validation") or log.VERBOSE:
      log.print_verbose(f"[yang_validation] Starting YANG validation for {phase} phase")
      log.print_verbose(f"[yang_validation] JSON structure keys: {list(topo_json.keys())}")

    instance = dm.from_raw(topo_json)

    if log.debug_active("yang_validation") or log.VERBOSE:
      log.print_verbose(f"[yang_validation] Successfully parsed JSON into YANG instance for {phase} phase")

    instance.validate(ValidationScope.all, ContentType.all)

    if log.debug_active("yang_validation") or log.VERBOSE:
      log.print_verbose(f"[yang_validation] YANG validation passed for {phase} phase")

  except RawMemberError as ex:
    # RawMemberError occurs during from_raw when JSON structure doesn't match YANG model
    error_path = getattr(ex, 'path', str(ex))
    errors.append(f"YANG validation failed: {error_path}")

    if log.debug_active("yang_validation") or log.VERBOSE:
      errors.append(f"Traceback: {traceback.format_exc()}")

  except (SemanticError, YangTypeError) as ex:
    # These are expected validation errors - return them as error messages
    errors.append(f"YANG validation failed: {str(ex)}")

    if log.debug_active("yang_validation") or log.VERBOSE:
      errors.append(f"Traceback: {traceback.format_exc()}")

  except Exception as ex:
    errors.append(f"YANG validation failed: {str(ex)}")
    if log.debug_active("yang_validation") or log.VERBOSE:
      errors.append(f"Traceback: {traceback.format_exc()}")

  return errors


def _validate_at_phase(topology: Box, phase: str) -> None:
  """
  Internal helper to validate topology at a specific transformation phase.

  Args:
    topology: The topology Box structure
    phase: The transformation phase ('init' or 'post_transform')
  """
  yang_config = topology.defaults.get("yang_validation", Box({}))

  # Check if validation is enabled for this phase
  validate_phase = yang_config.get("validate_phase", "post_transform")
  if phase != validate_phase:
    if log.debug_active("yang_validation"):
      print(f"YANG validation skipped for phase: {phase} (configured for: {validate_phase})")
    return

  # Get model path
  model_path = yang_config.get("model", "package:extra/yang_validation/model/netlab-topology.yang")

  # Check if model exists
  try:
    model_file = load_yang_model_path(model_path)
    if not model_file.exists():
      # Model not found, skip validation
      if log.debug_active("yang_validation"):
        print(f"YANG model not found: {model_path}, skipping validation")
      return
  except FileNotFoundError:
    # Model not found, skip validation
    if log.debug_active("yang_validation"):
      print(f"YANG model not found: {model_path}, skipping validation")
    return
  except Exception as ex:
    # Error checking file existence, skip validation
    if log.debug_active("yang_validation"):
      print(f"Error checking YANG model: {ex}, skipping validation")
    return

  # Validate topology
  errors = validate_topology_yang(topology, model_path, phase=phase)

  # Report errors if any
  if errors:
    log.error(f"YANG validation failed at {phase} phase", module="yang_validation")
    for error in errors:
      log.error(f"  {error}", module="yang_validation")
  elif log.debug_active("yang_validation"):
    print(f"YANG validation passed at {phase} phase")


def init(topology: Box) -> None:
  """
  Plugin initialization hook: Validate topology at init phase if configured.

  This hook is called during plugin initialization, before topology transformation.
  It validates the topology at the init phase if validate_phase is set to 'init'.
  """
  _validate_at_phase(topology, "init")


def post_transform(topology: Box) -> None:
  """
  Post-transform hook: Validate topology against YANG model.

  This hook is called after all topology transformation is complete.
  It validates the topology against the configured YANG model and reports any errors.

  Note: Including the plugin in the topology automatically enables validation.
  """
  _validate_at_phase(topology, "post_transform")

