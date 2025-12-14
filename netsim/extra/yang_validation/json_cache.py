#
# JSON Cache functionality for YANG validation plugin
#
# Handles incremental building and loading of JSON cache files
#
import importlib.util
import json
import os
import typing
from pathlib import Path

from box import Box

from netsim import __version__ as netlab_version
from netsim.utils import files as _files
from netsim.utils import log
from netsim.utils import read as _read

# ============================================================================
# Constants
# ============================================================================

DEFAULT_CACHE_FILENAME = "netlab.cache.json"


# ============================================================================
# Module-level tracking for JSON cache building
# ============================================================================

_cache_tracking_enabled = False
_cache_tracked_files: dict = {}
_cache_output_path: typing.Optional[str] = None
_original_read_yaml = None

# JSON cache data storage (for reading from cache)
_cache_data: typing.Optional[dict] = None
_original_read_from_cache = None


# ============================================================================
# Schema Loading and Validation
# ============================================================================


def _get_schema_path() -> Path:
  """Get path to cache schema file"""
  schema_path = Path(__file__).parent / "cache_schema.json"
  return schema_path


def _load_schema() -> typing.Optional[dict]:
  """Load JSON schema for cache validation"""
  schema_path = _get_schema_path()
  if not schema_path.exists():
    log.warning(text=f"JSON schema not found at {schema_path}", module="yang_validation")
    return None

  try:
    with open(schema_path, "r") as f:
      return json.load(f)
  except Exception as ex:
    log.warning(text=f"Error loading JSON schema: {ex}", module="yang_validation")
    return None


def _validate_json_cache(data: dict, schema: dict) -> bool:
  """Validate JSON cache data against schema"""
  # Check if jsonschema is available
  if importlib.util.find_spec("jsonschema") is None:
    # jsonschema not available, skip validation
    return True  # Don't fail if jsonschema is not available

  # Handle both old and new jsonschema API
  try:
    # jsonschema v4+ API - validate is a function, not a method
    from jsonschema import validate  # type: ignore[import-untyped]
    from jsonschema.exceptions import ValidationError  # type: ignore[import-untyped]
  except (ImportError, AttributeError):
    # Fallback for older jsonschema versions (< v4)
    import jsonschema  # type: ignore[import-untyped]

    validate = getattr(jsonschema, "validate", None)
    if validate is None:
      # Last resort: try validators module
      from jsonschema.validators import validate  # type: ignore[import-untyped,no-redef]
    try:
      from jsonschema.exceptions import ValidationError  # type: ignore[import-untyped]
    except ImportError:
      ValidationError = getattr(jsonschema, "ValidationError", Exception)  # type: ignore[attr-defined]

  try:
    validate(instance=data, schema=schema)
    return True
  except ValidationError as ex:
    log.error(f"JSON cache validation failed: {ex.message}", module="yang_validation")
    if ex.path:
      log.error(f"  Path: {'.'.join(str(p) for p in ex.path)}", module="yang_validation")
    return False
  except Exception as ex:
    log.warning(text=f"Error during JSON cache validation: {ex}", module="yang_validation")
    return True  # Don't fail on validation errors, just warn


# ============================================================================
# Cache Data Management
# ============================================================================


def set_cache_data(cache_data: typing.Optional[dict]) -> None:
  """
  Set the cache data dictionary to use for reading from JSON cache.

  Args:
    cache_data: Dictionary mapping filenames to file entries, or None to disable cache
  """
  global _cache_data
  _cache_data = cache_data


def read_from_cache(filename: str) -> typing.Optional[Box]:
  """
  Read a file from the JSON cache.

  Args:
    filename: The filename to look up in the cache

  Returns:
    Box object with the file content if found in cache, None otherwise
  """
  global _cache_data

  if _cache_data is None:
    return None

  # Try to find the file in cache using various key formats
  cache_key = None

  # First try exact match
  if filename in _cache_data:
    cache_key = filename
  else:
    # Try with absolute path
    try:
      abs_path = str(_files.absolute_path(filename))
      if abs_path in _cache_data:
        cache_key = abs_path
    except:
      pass

  # Try package: prefix format
  if cache_key is None and filename.startswith("package:"):
    if filename in _cache_data:
      cache_key = filename
    else:
      # Try without package: prefix
      try:
        no_package = filename.replace("package:", "")
        for key in _cache_data.keys():
          if key.endswith(no_package) or no_package in key:
            cache_key = key
            break
      except:
        pass

  if cache_key is None:
    return None

  file_entry = _cache_data.get(cache_key)
  if file_entry is None:
    return None

  # Extract content from file entry
  content = file_entry.get("content")
  if content is None:
    return None

  # Convert to Box object
  try:
    return Box(content, default_box=True, box_dots=True, default_box_none_transform=False)
  except Exception as ex:
    if log.debug_active("yang_validation"):
      log.debug(f"Failed to convert cached file {filename} to Box: {ex}", module="yang_validation")
    return None


def override_read_from_cache() -> None:
  """
  Override _read_from_cache in the read module to use JSON cache.

  This replaces the default _read_from_cache function with a version that
  first checks the JSON cache before falling back to the normal cache.
  """
  global _original_read_from_cache

  if _original_read_from_cache is None:
    _original_read_from_cache = _read._read_from_cache

  def json_cache_read_from_cache(filename: str) -> typing.Optional[Box]:
    """
    Override of _read_from_cache that checks JSON cache first.

    First checks JSON cache, then falls back to normal cache.
    """
    # Check JSON cache first
    json_result = read_from_cache(filename)
    if json_result is not None:
      return json_result

    # Fall back to original cache
    return _original_read_from_cache(filename)

  # Replace the function in the read module
  _read._read_from_cache = json_cache_read_from_cache


def restore_read_from_cache() -> None:
  """
  Restore the original _read_from_cache function in the read module.
  """
  global _original_read_from_cache

  if _original_read_from_cache is not None:
    _read._read_from_cache = _original_read_from_cache
    _original_read_from_cache = None


# ============================================================================
# Cache Loading
# ============================================================================


def load_from_json(json_file: str, validate: bool = True) -> typing.Optional[dict]:
  """
  Load the consolidated JSON file.

  Args:
    json_file: Path to the JSON cache file
    validate: Whether to validate against schema (default: True)

  Returns:
    Full consolidated dictionary (with version, files, etc.) or None if file doesn't exist or is invalid
  """
  if not os.path.isfile(json_file):
    return None

  try:
    with open(json_file, "r") as f:
      consolidated = json.load(f)

    # Check netlab version compatibility
    cache_version = consolidated.get("netlab_version")
    if cache_version != netlab_version:
      log.error(f"JSON cache {json_file} was created with netlab version {cache_version}", module="yang_validation")
      log.error(f"Current netlab version is {netlab_version}", module="yang_validation")
      log.error("Cache file is incompatible and must be regenerated", module="yang_validation")
      return None

    # Validate against schema if requested
    if validate:
      schema = _load_schema()
      if schema:
        if not _validate_json_cache(consolidated, schema):
          log.error(f"JSON cache {json_file} does not match schema", module="yang_validation")
          log.error("Cache file may be corrupted or from an incompatible version", module="yang_validation")
          return None

    return consolidated
  except json.JSONDecodeError as ex:
    log.error(f"Invalid JSON in cache file {json_file}: {ex}", module="yang_validation")
    return None
  except Exception as ex:
    log.warning(text=f"Error loading JSON cache {json_file}: {ex}", module="yang_validation")
    return None


def set_json_cache(json_file: str) -> None:
  """
  Set the JSON cache file to use for loading YAML files.
  This will cause read_yaml() to check the JSON cache before reading YAML files.

  This is a convenience function that loads the JSON cache and sets up the override
  of _read_from_cache in a single call.

  Args:
    json_file: Path to the consolidated JSON cache file
  """
  consolidated = load_from_json(json_file, validate=True)
  if consolidated is None:
    log.warning(
      text=f"Failed to load JSON cache from {json_file}, falling back to YAML files", module="yang_validation"
    )
    set_cache_data(None)
  else:
    # Extract just the files dictionary for use in read_yaml
    cache_data = consolidated.get("files") or {}
    set_cache_data(cache_data)
    override_read_from_cache()

    file_count = len(cache_data)
    cache_version = consolidated.get("netlab_version", "unknown")
    log.info(
      f"Using JSON cache from {json_file} (netlab {cache_version}, {file_count} files)", module="yang_validation"
    )


# ============================================================================
# Incremental Cache Building
# ============================================================================


def start_tracking(topology: Box) -> None:
  """
  Start tracking files for incremental JSON cache building.

  This wraps read_yaml to track all files that are read, building the cache incrementally.
  """
  global _cache_tracking_enabled, _cache_tracked_files, _cache_output_path, _original_read_yaml

  yang_config = topology.defaults.get("yang_validation", Box({}))

  # Check if JSON cache building is enabled (default: enabled if plugin is used)
  json_cache_enabled = yang_config.get("json_cache_enabled", True)
  if not json_cache_enabled:
    if log.debug_active("yang_validation"):
      log.debug("JSON cache building disabled in configuration", module="yang_validation")
    return

  # Get JSON cache file path from configuration
  json_cache_path = yang_config.get("json_cache", None)

  # If not specified in config, check environment variable
  if not json_cache_path:
    json_cache_path = os.environ.get("NETLAB_JSON_CACHE")

  # If we have a cache path and it exists, try to load existing cache
  if json_cache_path and os.path.isfile(json_cache_path):
    try:
      set_json_cache(json_cache_path)
      if _cache_data is not None:
        # Cache was successfully loaded, don't track if we're using an existing cache
        if log.debug_active("yang_validation"):
          log.debug(f"JSON cache loaded from: {json_cache_path}", module="yang_validation")
        return
      # Cache loading failed, continue to build new cache (will overwrite the file)
    except Exception as ex:
      log.warning(text=f"Failed to load JSON cache from {json_cache_path}: {ex}", module="yang_validation")
      # Continue to build new cache (will overwrite the file)

  # Determine cache output path
  if not json_cache_path:
    # Auto-generate cache path based on topology file if available
    # Try to get topology file from topology.input (set during load)
    try:
      if topology.get("input"):
        topo_file = topology.input[0] if isinstance(topology.input, list) else topology.input
        if topo_file and not topo_file.startswith("package:"):
          # Generate cache file name based on topology file (in same directory)
          topo_path = Path(topo_file)
          json_cache_path = str(topo_path.parent / f"{topo_path.stem}.cache.json")
        else:
          # Package file or no valid input, use default in current directory
          json_cache_path = DEFAULT_CACHE_FILENAME
      else:
        # No topology input, use default in current directory
        json_cache_path = DEFAULT_CACHE_FILENAME
    except Exception as ex:
      if log.debug_active("yang_validation"):
        log.debug(f"Failed to generate cache path from topology.input: {ex}, using default", module="yang_validation")
      # json_cache_path not set, use default
      json_cache_path = DEFAULT_CACHE_FILENAME

  # Set up tracking (don't reset if already tracking)
  _cache_output_path = json_cache_path
  if not _cache_tracking_enabled:
    _cache_tracked_files = {}
  _cache_tracking_enabled = True

  # Wrap read_yaml to track files
  if _original_read_yaml is None:
    _original_read_yaml = _read.read_yaml

  def tracking_read_yaml(
    filename: typing.Optional[str] = None, string: typing.Optional[str] = None
  ) -> typing.Optional[Box]:
    """Wrapper around read_yaml that tracks all files read and updates cache"""
    # Call original read_yaml (this may reload from disk if mtime is newer)
    result = _original_read_yaml(filename=filename, string=string)

    # Track/update this file if we're tracking and it's a file (not a string)
    if _cache_tracking_enabled and filename and not string and result is not None:
      # Normalize the filename for tracking
      if filename.startswith("package:"):
        cache_key = filename
      else:
        try:
          cache_key = str(_files.absolute_path(filename))
        except:
          cache_key = filename

      # Track this file if we haven't seen it yet, or update if already tracked
      # Handle both Box objects (dicts) and lists
      if isinstance(result, Box):
        content = result.to_dict()
      elif isinstance(result, (list, dict)):
        content = result
      else:
        content = {}

      # Get mtime for all files (including package files)
      mtime = None
      try:
        abs_path = _files.absolute_path(filename)
        if os.path.isfile(abs_path):
          mtime = os.path.getmtime(abs_path)
      except:
        pass

      file_entry = {"content": content, "source": filename, "package": filename.startswith("package:")}

      if mtime is not None:
        file_entry["mtime"] = mtime

      _cache_tracked_files[cache_key] = file_entry

    return result

  # Replace read_yaml with tracking version
  _read.read_yaml = tracking_read_yaml

  if log.debug_active("yang_validation"):
    log.debug(f"JSON cache tracking enabled, will save to: {json_cache_path}", module="yang_validation")


def stop_tracking_and_save(topology: Box) -> None:
  """
  Stop tracking and save the incrementally built JSON cache.

  This hook is called after all transformation and validation is complete.
  It saves the tracked files to the JSON cache file.
  """
  global _cache_tracking_enabled, _cache_tracked_files, _cache_output_path, _original_read_yaml

  if not _cache_tracking_enabled or not _cache_output_path:
    return

  # If no files were tracked, we still want to save an empty cache if tracking was enabled
  # This can happen if all files were already in cache and not re-read during transform
  if not _cache_tracked_files:
    if log.debug_active("yang_validation"):
      log.debug("No files tracked for JSON cache, saving empty cache", module="yang_validation")
    # Continue to save an empty cache structure

  # Get topology file path if available
  topology_file = None
  try:
    if topology.get("input"):
      topology_file = topology.input[0] if isinstance(topology.input, list) else topology.input
  except:
    pass

  # Create the consolidated structure
  consolidated = {
    "version": "1.0",
    "netlab_version": netlab_version,
    "topology_file": topology_file,
    "files": _cache_tracked_files,
    "file_count": len(_cache_tracked_files),
  }

  # Validate against schema before writing
  schema = _load_schema()
  if schema:
    if not _validate_json_cache(consolidated, schema):
      log.warning("Generated JSON cache does not match schema, but writing anyway", module="yang_validation")

  # Write to JSON file
  output_path = Path(_cache_output_path)
  output_path.parent.mkdir(parents=True, exist_ok=True)

  try:
    with open(output_path, "w") as f:
      json.dump(consolidated, f, indent=2, default=str)

    log.info(f"JSON cache saved: {_cache_output_path} ({len(_cache_tracked_files)} files)", module="yang_validation")

    # Update cache data so subsequent reads can use the newly saved cache
    set_cache_data(_cache_tracked_files)
    override_read_from_cache()
  except Exception as ex:
    log.warning(text=f"Failed to save JSON cache to {_cache_output_path}: {ex}", module="yang_validation")

  # Restore original read_yaml
  if _original_read_yaml is not None:
    _read.read_yaml = _original_read_yaml
    _original_read_yaml = None

  # Reset tracking
  _cache_tracking_enabled = False
  _cache_tracked_files = {}
  _cache_output_path = None
