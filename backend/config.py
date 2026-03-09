"""Configuration loader for LLM Council.

Loads and saves council_config.json from the data/ directory.
Runs orphan detection on every load so stale chairman/summarization
references are caught immediately rather than at call time.

Sprint 7 additions:
- Password hashing (bcrypt) and verification
- API key encryption at rest (Fernet + PBKDF2)
- JWT session token generation and validation
- Salt and secret file management
"""

import base64
import copy
import json
import os
import secrets
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

import bcrypt
import jwt
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Directory paths — DATA_DIR is exported so storage.py can import it
DATA_DIR = "data/conversations"
_CONFIG_PATH = Path("data/council_config.json")
_DATA_ROOT = Path("data")
_SALT_PATH = Path("data/.salt")
_SECRET_PATH = Path("data/.secret")

# JWT settings
_JWT_ALGORITHM = "HS256"
_JWT_EXPIRY_SECONDS = 24 * 60 * 60  # 24 hours

# In-memory cache for the Fernet key (derived from password on login)
# This is set after a successful login and cleared on server restart.
_fernet_key: Optional[bytes] = None


# ---------------------------------------------------------------------------
# Data directory management
# ---------------------------------------------------------------------------

def _ensure_data_dirs():
    """Create data/ and data/conversations/ if they don't exist."""
    _DATA_ROOT.mkdir(parents=True, exist_ok=True)
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Salt management — used for PBKDF2 key derivation
# ---------------------------------------------------------------------------

def _get_or_create_salt() -> bytes:
    """Load salt from data/.salt, or generate and persist a new one."""
    _ensure_data_dirs()
    if _SALT_PATH.exists():
        return _SALT_PATH.read_bytes()
    salt = os.urandom(16)
    _SALT_PATH.write_bytes(salt)
    return salt


def _derive_fernet_key(password: str) -> bytes:
    """Derive a Fernet-compatible key from a password using PBKDF2."""
    salt = _get_or_create_salt()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=600_000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))
    return key


# ---------------------------------------------------------------------------
# JWT secret management
# ---------------------------------------------------------------------------

def _get_or_create_jwt_secret() -> str:
    """Load JWT signing secret from data/.secret, or generate and persist one."""
    _ensure_data_dirs()
    if _SECRET_PATH.exists():
        return _SECRET_PATH.read_text(encoding="utf-8").strip()
    secret = secrets.token_hex(32)
    _SECRET_PATH.write_text(secret, encoding="utf-8")
    return secret


# ---------------------------------------------------------------------------
# API key encryption / decryption
# ---------------------------------------------------------------------------

def _encrypt_api_key(plaintext: str, fernet_key: bytes) -> str:
    """Encrypt a plaintext API key. Returns empty string for empty keys."""
    if not plaintext:
        return ""
    f = Fernet(fernet_key)
    return f.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def _decrypt_api_key(ciphertext: str, fernet_key: bytes) -> str:
    """Decrypt an encrypted API key. Returns empty string for empty values."""
    if not ciphertext:
        return ""
    try:
        f = Fernet(fernet_key)
        return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except (InvalidToken, Exception) as e:
        print(f"Warning: could not decrypt API key ({e}). Returning empty.")
        return ""


def _encrypt_model_keys(config: Dict[str, Any], fernet_key: bytes) -> Dict[str, Any]:
    """Return a deep copy of config with all api_key fields encrypted."""
    encrypted = copy.deepcopy(config)
    for model in encrypted.get("available_models", []):
        model["api_key"] = _encrypt_api_key(model.get("api_key", ""), fernet_key)
    return encrypted


def _decrypt_model_keys(config: Dict[str, Any], fernet_key: bytes) -> Dict[str, Any]:
    """Return a deep copy of config with all api_key fields decrypted."""
    decrypted = copy.deepcopy(config)
    for model in decrypted.get("available_models", []):
        model["api_key"] = _decrypt_api_key(model.get("api_key", ""), fernet_key)
    return decrypted


# ---------------------------------------------------------------------------
# Password management
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """Hash a password with bcrypt. Returns the hash as a string."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def is_password_set() -> bool:
    """Check if a password has been set (config file exists with password_hash)."""
    _ensure_data_dirs()
    if not _CONFIG_PATH.exists():
        return False
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
        return bool(config.get("password_hash"))
    except (json.JSONDecodeError, OSError):
        return False


def set_initial_password(password: str):
    """
    Set the password during first-run setup.
    Creates or updates council_config.json with the password hash.
    Also initializes the Fernet key in memory and encrypts any existing keys.
    """
    global _fernet_key
    _ensure_data_dirs()

    # Derive and cache the Fernet key
    _fernet_key = _derive_fernet_key(password)

    # Load existing config or start fresh
    if _CONFIG_PATH.exists():
        try:
            with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)
        except (json.JSONDecodeError, OSError):
            config = {}
    else:
        config = {}

    # Set password hash
    config["password_hash"] = hash_password(password)

    # Encrypt any existing plaintext API keys
    config = _encrypt_model_keys(config, _fernet_key)

    # Strip internal keys and save
    clean = {k: v for k, v in config.items() if not k.startswith("_")}
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2)


def change_password(old_password: str, new_password: str) -> bool:
    """
    Change the password. Re-encrypts all API keys with the new derived key.
    Returns True on success, False if old password is wrong.
    """
    global _fernet_key

    # Load raw config to check password
    if not _CONFIG_PATH.exists():
        return False

    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        raw_config = json.load(f)

    if not verify_password(old_password, raw_config.get("password_hash", "")):
        return False

    # Decrypt all keys with old key
    old_fernet_key = _derive_fernet_key(old_password)
    decrypted = _decrypt_model_keys(raw_config, old_fernet_key)

    # Re-encrypt with new key
    # Need a new salt for the new password derivation? No — we keep the same salt.
    # The salt is for PBKDF2 derivation, and changing password just changes the input.
    new_fernet_key = _derive_fernet_key(new_password)
    encrypted = _encrypt_model_keys(decrypted, new_fernet_key)

    # Update password hash
    encrypted["password_hash"] = hash_password(new_password)

    # Cache new key
    _fernet_key = new_fernet_key

    # Save
    clean = {k: v for k, v in encrypted.items() if not k.startswith("_")}
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2)

    return True


# ---------------------------------------------------------------------------
# JWT session tokens
# ---------------------------------------------------------------------------

def create_session_token() -> str:
    """Create a signed JWT session token valid for 24 hours of inactivity."""
    secret = _get_or_create_jwt_secret()
    payload = {
        "iat": int(time.time()),
        "exp": int(time.time()) + _JWT_EXPIRY_SECONDS,
    }
    return jwt.encode(payload, secret, algorithm=_JWT_ALGORITHM)


def validate_session_token(token: str) -> bool:
    """Validate a JWT session token. Returns True if valid and not expired."""
    secret = _get_or_create_jwt_secret()
    try:
        jwt.decode(token, secret, algorithms=[_JWT_ALGORITHM])
        return True
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return False


# ---------------------------------------------------------------------------
# Fernet key state management
# ---------------------------------------------------------------------------

def login_and_cache_key(password: str) -> bool:
    """
    Verify password and cache the Fernet key in memory if correct.
    Called on successful login so the server can decrypt API keys.
    Returns True if password is correct.
    """
    global _fernet_key

    if not _CONFIG_PATH.exists():
        return False

    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        raw_config = json.load(f)

    if not verify_password(password, raw_config.get("password_hash", "")):
        return False

    _fernet_key = _derive_fernet_key(password)
    return True


def get_fernet_key() -> Optional[bytes]:
    """Return the cached Fernet key, or None if not yet logged in."""
    return _fernet_key


# ---------------------------------------------------------------------------
# Config loading and saving
# ---------------------------------------------------------------------------

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
    Load council_config.json from disk, decrypt API keys, and run orphan detection.

    API keys are stored encrypted on disk. If the Fernet key is cached in memory
    (after login), keys are decrypted transparently. If not yet logged in,
    keys remain encrypted (will be empty/garbled — endpoints requiring decrypted
    keys should check via get_fernet_key() first).

    Returns:
        Config dict with decrypted keys and '_warnings' list.
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

    # Decrypt API keys if we have the Fernet key
    if _fernet_key:
        config = _decrypt_model_keys(config, _fernet_key)

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

    API keys are encrypted before writing to disk. Internal keys (those
    starting with '_') are stripped before writing.

    Args:
        config: Config dict with plaintext keys (may include '_warnings' — will be stripped)
    """
    _ensure_data_dirs()

    # Strip internal-only keys before persisting
    clean = {k: v for k, v in config.items() if not k.startswith("_")}

    # Encrypt API keys if we have the Fernet key
    if _fernet_key:
        clean = _encrypt_model_keys(clean, _fernet_key)

    # Preserve the password hash from the existing file (callers don't pass it)
    if _CONFIG_PATH.exists():
        try:
            with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                existing = json.load(f)
            if "password_hash" in existing and "password_hash" not in clean:
                clean["password_hash"] = existing["password_hash"]
        except (json.JSONDecodeError, OSError):
            pass

    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2)


# ---------------------------------------------------------------------------
# Config accessors (unchanged from Sprint 1)
# ---------------------------------------------------------------------------

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
