#
# YANG validation plugin
#
import json
import re
import traceback
import typing
from pathlib import Path

from box import Box

# Import JSON cache functionality
from netsim.extra.yang_validation import json_cache
from netsim.utils import files as _files
from netsim.utils import log

# ============================================================================
# YANG Validation Functions
# ============================================================================


def _dump_model_to_file(topology: Box, topo_json: dict, phase: str) -> None:
  """
  Dump the topology JSON model to a file if dump_model is enabled.

  Args:
    topology: The topology Box structure
    topo_json: The JSON representation of the topology (ready for validation)
    phase: The validation phase name (used in filename)
  """
  yang_config = topology.defaults.get("yang_validation", Box({}))
  dump_model = yang_config.get("dump_model", False)

  if not dump_model:
    return

  try:
    from pathlib import Path

    # Determine the lab directory from topology.input
    # topology.input is a list containing the topology file path(s)
    dump_dir = Path(".")  # Default to current directory
    if "input" in topology and isinstance(topology.input, list) and len(topology.input) > 0:
      topo_path = topology.input[0]
      # Handle package: paths
      if isinstance(topo_path, str) and not topo_path.startswith("package:"):
        topo_file = Path(topo_path)
        if topo_file.exists():
          dump_dir = topo_file.parent
        else:
          # If path doesn't exist, try to resolve it
          try:
            dump_dir = Path(topo_path).parent.resolve()
          except Exception:
            pass  # Fall back to current directory

    # Create dump file in the lab directory
    dump_filename = dump_dir / f"yang-validation-{phase}.json"
    with open(dump_filename, "w") as f:
      json.dump(topo_json, f, indent=2, default=str)
    if log.debug_active("yang_validation") or log.VERBOSE:
      log.info(f"Dumped {phase} phase model to {dump_filename}", module="yang_validation")
  except Exception as ex:
    log.warning(f"Failed to dump model for {phase} phase: {ex}", module="yang_validation")


def topology_to_json(topology: Box, yang_model_path: typing.Optional[str] = None) -> dict:
  """
  Convert topology Box structure to JSON-compatible dictionary for YANG validation

  yangson expects JSON data matching the YANG model structure. The data should
  be wrapped in the namespace-qualified container name.

  Args:
    topology: The topology Box structure
    yang_model_path: Optional path to YANG model file to extract namespace from
  """
  # Convert Box to dict and handle special cases
  topo_dict = topology.to_dict()

  # Remove all internal/private keys starting with '_' before YANG validation
  # Recursively remove underscore-prefixed keys from nested structures
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

  # Transform nodes from dictionary to list format for YANG validation
  # YANG lists must be arrays, but netlab uses dictionaries keyed by node name
  if "nodes" in topo_dict and isinstance(topo_dict["nodes"], dict):
    nodes_list = []
    for node_name, node_data in topo_dict["nodes"].items():
      if isinstance(node_data, dict):
        node_data["name"] = node_name
        nodes_list.append(node_data)
      else:
        # If node_data is not a dict, create a simple node entry
        nodes_list.append({"name": node_name})
    topo_dict["nodes"] = nodes_list

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


def _create_yang_library(yang_content: str, yang_dir: str) -> str:
  """
  Extract module metadata from YANG content and create YANG library JSON.
  Handles imports by including imported modules in the library.

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
    phase: Phase name for dump_model filename and logging (e.g., 'init', 'setup', 'post_transform')

  Returns list of error messages, empty list if validation passes
  """
  errors: typing.List[str] = []

  # Check if yangson is available
  try:
    from yangson import DataModel  # type: ignore[import-untyped]
    from yangson.enumerations import ContentType, ValidationScope  # type: ignore[import-untyped]
    from yangson.exceptions import SchemaError, SemanticError, YangTypeError  # type: ignore[import-untyped]
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
    instance = dm.from_raw(topo_json)

    # Dump model to file if dump_model is enabled (just before validation)
    _dump_model_to_file(topology, topo_json, phase)

    instance.validate(ValidationScope.all, ContentType.all)
  except (SemanticError, YangTypeError) as ex:
    # These are expected validation errors - return them as error messages
    errors.append(f"YANG validation failed: {str(ex)}")
  except Exception as ex:
    errors.append(f"YANG validation failed: {str(ex)}")
    if log.debug_active("yang"):
      errors.append(f"Traceback: {traceback.format_exc()}")

  return errors


# ============================================================================
# Plugin Hooks
# ============================================================================


def init(topology: Box) -> None:
  """
  Plugin initialization hook: Set up incremental JSON cache tracking and validate at init phase.

  This hook is called during plugin initialization, before topology transformation.
  It sets up JSON cache tracking and validates the topology at the init phase.
  """
  # Start JSON cache tracking
  json_cache.start_tracking(topology)

  # Validate at init phase if enabled (before any transformation)
  # This validates the topology as loaded, after defaults are merged but before setup phase
  # Note: At this point, defaults.sources and topology.input are already present
  _validate_at_phase(topology, "init")


def _validate_at_phase(topology: Box, phase: str) -> None:
  """
  Internal helper to validate topology at a specific transformation phase.

  Args:
    topology: The topology Box structure
    phase: The transformation phase ('init', 'setup', 'pre_transform', 'post_node_transform',
           'post_link_transform', 'post_transform')
  """
  yang_config = topology.defaults.get("yang_validation", Box({}))

  # Check if validation is enabled for this phase
  validate_phases = yang_config.get("validate_phases", ["post_transform"])
  if phase not in validate_phases:
    if log.debug_active("yang_validation"):
      log.debug(f"YANG validation skipped for phase: {phase}", module="yang_validation")
    return

  # Get phase-specific model path or use default
  # Default is the post-transform model (most complete)
  model_base = yang_config.get("model", "package:extra/yang_validation/model/netlab-topology-post-transform.yang")

  # Construct YANG filename based on base + phase with '_' replaced by '-'
  # Extract the base prefix (everything before the last hyphen-separated segment)
  # e.g., "netlab-topology-post-transform.yang" -> base prefix is "netlab-topology"
  # For phase "post_node_transform" -> "netlab-topology-post-node-transform.yang"

  # Convert phase name: replace underscores with hyphens
  phase_filename = phase.replace("_", "-")

  # Extract base prefix from model_base
  # The base prefix is always "netlab-topology" (first two hyphen-separated parts)
  # e.g., "netlab-topology-post-transform" -> "netlab-topology"
  if "package:" in model_base:
    path_parts = model_base.split("/")
    filename = path_parts[-1].replace(".yang", "")
  else:
    filename = model_base.replace(".yang", "")
    path_parts = None

  # Extract base prefix: take first two hyphen-separated parts
  # This handles cases like "netlab-topology-post-transform" -> "netlab-topology"
  parts = filename.split("-")
  if len(parts) >= 2:
    base_prefix = "-".join(parts[:2])  # "netlab-topology"
  else:
    base_prefix = filename

  # Construct new filename
  new_filename = f"{base_prefix}-{phase_filename}.yang"

  # Reconstruct path
  if path_parts:
    path_parts[-1] = new_filename
    yang_model_path = "/".join(path_parts)
  else:
    yang_model_path = new_filename

  # Check if phase-specific model exists, otherwise skip validation
  try:
    from netsim.utils import files as _files

    if not _files.absolute_path(yang_model_path).exists():
      # Phase-specific model not found, skip validation
      if log.debug_active("yang_validation"):
        log.debug(
          f"YANG model not found for phase {phase}: {yang_model_path}, skipping validation", module="yang_validation"
        )
      return
  except Exception as ex:
    # Error checking file existence, skip validation
    if log.debug_active("yang_validation"):
      log.debug(f"Error checking YANG model for phase {phase}: {ex}, skipping validation", module="yang_validation")
    return

  # Validate topology
  errors = validate_topology_yang(topology, yang_model_path, phase=phase)

  # Report errors if any
  if errors:
    log.error(f"YANG validation failed at {phase} phase", module="yang_validation")
    for error in errors:
      log.error(f"  {error}", module="yang_validation")
  elif log.debug_active("yang_validation"):
    log.debug(f"YANG validation passed at {phase} phase", module="yang_validation")


def pre_transform(topology: Box) -> None:
  """
  Pre-transform hook: Validate topology after setup and before data transformation.

  This hook is called after pre_transform plugin hooks execute.
  It validates the topology structure before node and link transformation begins.
  """
  _validate_at_phase(topology, "pre_transform")


def post_node_transform(topology: Box) -> None:
  """
  Post-node-transform hook: Validate topology after node transformation.

  This hook is called after node data transformation is complete.
  Nodes now have IDs, management IPs, and loopback addresses assigned.
  """
  _validate_at_phase(topology, "post_node_transform")


def post_link_transform(topology: Box) -> None:
  """
  Post-link-transform hook: Validate topology after link transformation.

  This hook is called after link data transformation is complete.
  Links now have interfaces created, and node interfaces are populated.
  """
  _validate_at_phase(topology, "post_link_transform")


def post_transform(topology: Box) -> None:
  """
  Post-transform hook: Validate topology against YANG model.

  This hook is called after all topology transformation is complete.
  It validates the topology against the configured YANG model and reports any errors.

  Note: Including the plugin in the topology automatically enables validation.
  """
  _validate_at_phase(topology, "post_transform")


def cleanup(topology: Box) -> None:
  """
  Cleanup hook: Save the incrementally built JSON cache.

  This hook is called after all transformation and validation is complete.
  It saves the tracked files to the JSON cache file.
  """
  json_cache.stop_tracking_and_save(topology)
