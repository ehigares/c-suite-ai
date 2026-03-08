"""Configuration loader for LLM Council.

Loads and saves council_config.json from the data/ directory.
Runs orphan detection on every load so stale chairman/summarization
references are caught immediately rather than at call time.
"""

import json
from pathlib import Path
from typing import Dict, Any, List

# Directory paths — DATA_DIR is exported so storage.py can import it
DATA_DIR = "data/conversations"
_CONFIG_PATH = Path("data/council_config.json")
_DATA_ROOT = Path("data")


def _ensure_data_dirs():
    """Create data/ and data/conversations/ if they don't exist."""
    _DATA_ROOT.mkdir(parents=True, exist_ok=True)
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)


def _default_config() -> Dict[str, Any]:
    """Return a blank config — used when no config file exists yet."""
    return {
        "available_models": [],
        "chairman_id": None,
        "summarization_model_id": None,
        "favorites_council": [],
        "history_raw_exchanges": 3,
        "_warnings": [],
    }


def load_config() -> Dict[str, Any]:
    """
    Load council_config.json from disk and run orphan detection.

    Orphan detection: if chairman_id or summarization_model_id points to a
    model that no longer exists in available_models, the field is cleared and
    a warning key is added to the config dict so callers can surface it to users.

    The returned dict always has a '_warnings' list (may be empty).
    '_warnings' is never written back to disk.

    Returns:
        Config dict. Safe to use even if the file doesn't exist yet.
    """
    _ensure_data_dirs()

    if not _CONFIG_PATH.exists():
        return _default_config()

    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"Warning: could not read council_config.json ({e}). Using defaults.")
        return _default_config()

    # Ensure required keys exist (backward compatibility)
    config.setdefault("available_models", [])
    config.setdefault("chairman_id", None)
    config.setdefault("summarization_model_id", None)
    config.setdefault("favorites_council", [])
    config.setdefault("history_raw_exchanges", 3)
    config["_warnings"] = []

    # Build set of valid model IDs for orphan detection
    valid_ids = {m["id"] for m in config["available_models"]}

    # Check chairman
    if config["chairman_id"] and config["chairman_id"] not in valid_ids:
        print(f"Warning: chairman_id '{config['chairman_id']}' not in available_models — clearing.")
        config["chairman_id"] = None
        config["_warnings"].append("chairman_orphaned")

    # Check summarization model
    if config["summarization_model_id"] and config["summarization_model_id"] not in valid_ids:
        print(f"Warning: summarization_model_id '{config['summarization_model_id']}' not in available_models — clearing.")
        config["summarization_model_id"] = None
        config["_warnings"].append("summarization_orphaned")

    # Scrub favorites_council of any IDs that no longer exist
    original_favorites = config.get("favorites_council", [])
    config["favorites_council"] = [fid for fid in original_favorites if fid in valid_ids]

    return config


def save_config(config: Dict[str, Any]):
    """
    Save config to council_config.json.

    Internal keys (those starting with '_') are stripped before writing
    so they never end up on disk.

    Args:
        config: Config dict (may include internal '_warnings' key — will be stripped)
    """
    _ensure_data_dirs()

    # Strip internal-only keys before persisting
    clean = {k: v for k, v in config.items() if not k.startswith("_")}

    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2)


def get_chairman(config: Dict[str, Any]) -> Dict[str, Any] | None:
    """
    Look up the chairman model config dict by ID.

    Args:
        config: Loaded config dict

    Returns:
        Model config dict for the chairman, or None if not set / not found
    """
    chairman_id = config.get("chairman_id")
    if not chairman_id:
        return None
    for model in config.get("available_models", []):
        if model["id"] == chairman_id:
            return model
    return None


def get_summarization_model(config: Dict[str, Any]) -> Dict[str, Any] | None:
    """
    Look up the summarization model config dict by ID.

    Args:
        config: Loaded config dict

    Returns:
        Model config dict for the summarization model, or None if not set / not found
    """
    summ_id = config.get("summarization_model_id")
    if not summ_id:
        return None
    for model in config.get("available_models", []):
        if model["id"] == summ_id:
            return model
    return None


def get_models_by_ids(config: Dict[str, Any], ids: List[str]) -> List[Dict[str, Any]]:
    """
    Retrieve model config dicts for a list of IDs, preserving order.
    IDs not found in available_models are silently skipped.

    Args:
        config: Loaded config dict
        ids: List of model UUIDs

    Returns:
        List of model config dicts
    """
    id_to_model = {m["id"]: m for m in config.get("available_models", [])}
    return [id_to_model[mid] for mid in ids if mid in id_to_model]
