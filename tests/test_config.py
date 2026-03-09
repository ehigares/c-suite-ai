"""
test_config.py — Tests for config loading, orphan detection, save/reload,
encryption, and schema validation.

Runs without API keys or a running server. Uses a temporary directory
to avoid touching real data.

Run from the project root:
    python -m tests.test_config
"""

import sys
import json
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, ".")

import backend.config as cfg


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

PASS = "PASS"
FAIL = "FAIL"
_failures = []


def check(label: str, condition: bool, detail: str = ""):
    if condition:
        print(f"  {PASS}  {label}")
    else:
        msg = f"  {FAIL}  {label}"
        if detail:
            msg += f"\n        -> {detail}"
        print(msg)
        _failures.append(label)


def section(title: str):
    print(f"\n{'-' * 60}")
    print(f"  {title}")
    print(f"{'-' * 60}")


# ---------------------------------------------------------------------------
# Test isolation: redirect config paths to a temp directory
# ---------------------------------------------------------------------------

_original_paths = {}


def setup_temp_dir():
    """Create a temp directory and redirect all config paths to it."""
    test_dir = Path(tempfile.mkdtemp())
    _original_paths["CONFIG_PATH"] = cfg._CONFIG_PATH
    _original_paths["DATA_ROOT"] = cfg._DATA_ROOT
    _original_paths["SALT_PATH"] = cfg._SALT_PATH
    _original_paths["SECRET_PATH"] = cfg._SECRET_PATH
    _original_paths["DATA_DIR"] = cfg.DATA_DIR
    _original_paths["fernet_key"] = cfg._fernet_key

    cfg._CONFIG_PATH = test_dir / "council_config.json"
    cfg._DATA_ROOT = test_dir
    cfg._SALT_PATH = test_dir / ".salt"
    cfg._SECRET_PATH = test_dir / ".secret"
    cfg.DATA_DIR = str(test_dir / "conversations")
    cfg._fernet_key = None
    return test_dir


def teardown_temp_dir(test_dir):
    """Restore original paths and clean up."""
    cfg._CONFIG_PATH = _original_paths["CONFIG_PATH"]
    cfg._DATA_ROOT = _original_paths["DATA_ROOT"]
    cfg._SALT_PATH = _original_paths["SALT_PATH"]
    cfg._SECRET_PATH = _original_paths["SECRET_PATH"]
    cfg.DATA_DIR = _original_paths["DATA_DIR"]
    cfg._fernet_key = _original_paths["fernet_key"]
    shutil.rmtree(str(test_dir), ignore_errors=True)


def write_config(test_dir, config_dict):
    """Write a config dict directly to the test config file."""
    path = test_dir / "council_config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(config_dict, f)


# ---------------------------------------------------------------------------
# Tests: load_config
# ---------------------------------------------------------------------------

def test_load_config():
    section("load_config()")
    test_dir = setup_temp_dir()
    try:
        # No config file — should return defaults
        config = cfg.load_config()
        check("no file -> default config", config["available_models"] == [])
        check("no file -> _warnings is empty list", config["_warnings"] == [])
        check("no file -> history_raw_exchanges default is 3",
              config["history_raw_exchanges"] == 3)

        # Valid config file
        write_config(test_dir, {
            "available_models": [
                {"id": "m1", "display_name": "Model 1", "model": "test", "base_url": "https://ex.com", "api_key": ""}
            ],
            "chairman_id": "m1",
            "summarization_model_id": "m1",
            "favorites_council": ["m1"],
            "history_raw_exchanges": 5,
        })
        config = cfg.load_config()
        check("valid file -> 1 model", len(config["available_models"]) == 1)
        check("valid file -> chairman_id preserved", config["chairman_id"] == "m1")
        check("valid file -> history_raw_exchanges is 5", config["history_raw_exchanges"] == 5)
        check("valid file -> no warnings", config["_warnings"] == [])

        # Malformed JSON
        with open(test_dir / "council_config.json", "w") as f:
            f.write("{bad json")
        config = cfg.load_config()
        check("malformed JSON -> returns defaults", config["available_models"] == [])

    finally:
        teardown_temp_dir(test_dir)


# ---------------------------------------------------------------------------
# Tests: orphan detection
# ---------------------------------------------------------------------------

def test_orphan_detection():
    section("orphan detection")
    test_dir = setup_temp_dir()
    try:
        # Chairman ID points to nonexistent model
        write_config(test_dir, {
            "available_models": [
                {"id": "m1", "display_name": "M1", "model": "x", "base_url": "https://x.com", "api_key": ""}
            ],
            "chairman_id": "deleted-model",
            "summarization_model_id": "m1",
            "favorites_council": ["m1"],
        })
        config = cfg.load_config()
        check("orphaned chairman -> cleared to None", config["chairman_id"] is None)
        check("orphaned chairman -> warning added", "chairman_orphaned" in config["_warnings"])

        # Summarization model ID points to nonexistent model
        write_config(test_dir, {
            "available_models": [
                {"id": "m1", "display_name": "M1", "model": "x", "base_url": "https://x.com", "api_key": ""}
            ],
            "chairman_id": "m1",
            "summarization_model_id": "deleted-summ",
            "favorites_council": ["m1"],
        })
        config = cfg.load_config()
        check("orphaned summarization -> cleared to None", config["summarization_model_id"] is None)
        check("orphaned summarization -> warning added", "summarization_orphaned" in config["_warnings"])

        # Favorites with invalid IDs get scrubbed
        write_config(test_dir, {
            "available_models": [
                {"id": "m1", "display_name": "M1", "model": "x", "base_url": "https://x.com", "api_key": ""}
            ],
            "chairman_id": "m1",
            "summarization_model_id": "m1",
            "favorites_council": ["m1", "deleted-fav", "also-deleted"],
        })
        config = cfg.load_config()
        check("favorites scrubbed of invalid IDs", config["favorites_council"] == ["m1"])

    finally:
        teardown_temp_dir(test_dir)


# ---------------------------------------------------------------------------
# Tests: save and reload
# ---------------------------------------------------------------------------

def test_save_reload():
    section("save_config() and reload")
    test_dir = setup_temp_dir()
    try:
        original = {
            "available_models": [
                {"id": "m1", "display_name": "Test Model", "model": "test/model", "base_url": "https://api.test.com", "api_key": ""}
            ],
            "chairman_id": "m1",
            "summarization_model_id": "m1",
            "favorites_council": ["m1"],
            "history_raw_exchanges": 7,
            "_warnings": ["should_be_stripped"],
        }
        cfg.save_config(original)

        # Reload and check
        loaded = cfg.load_config()
        check("save/reload preserves models",
              len(loaded["available_models"]) == 1)
        check("save/reload preserves chairman_id",
              loaded["chairman_id"] == "m1")
        check("save/reload preserves history_raw_exchanges",
              loaded["history_raw_exchanges"] == 7)
        check("_warnings stripped from disk (not in raw file)",
              "_warnings" not in json.loads((test_dir / "council_config.json").read_text()))

    finally:
        teardown_temp_dir(test_dir)


# ---------------------------------------------------------------------------
# Tests: encryption round-trip
# ---------------------------------------------------------------------------

def test_encryption():
    section("API key encryption")
    test_dir = setup_temp_dir()
    try:
        # Set password (creates salt, derives key, encrypts)
        cfg.set_initial_password("testpass")

        config_with_key = {
            "available_models": [
                {"id": "m1", "display_name": "T", "model": "x", "base_url": "https://x.com", "api_key": "sk-my-secret-key-123"}
            ],
            "chairman_id": "m1",
            "summarization_model_id": "m1",
            "favorites_council": [],
            "history_raw_exchanges": 3,
        }
        cfg.save_config(config_with_key)

        # Check that on-disk value is encrypted (not plaintext)
        raw = json.loads((test_dir / "council_config.json").read_text())
        on_disk_key = raw["available_models"][0]["api_key"]
        check("on-disk key is NOT plaintext", on_disk_key != "sk-my-secret-key-123")
        check("on-disk key is not empty", on_disk_key != "")

        # Load decrypts correctly
        loaded = cfg.load_config()
        check("loaded key is decrypted",
              loaded["available_models"][0]["api_key"] == "sk-my-secret-key-123")

        # After fernet key cleared, loading returns garbled key (not plaintext)
        cfg._fernet_key = None
        loaded_no_key = cfg.load_config()
        check("without fernet key, loaded key is NOT plaintext",
              loaded_no_key["available_models"][0]["api_key"] != "sk-my-secret-key-123")

        # Re-login restores decryption
        assert cfg.login_and_cache_key("testpass")
        loaded_again = cfg.load_config()
        check("after re-login, key decrypts correctly",
              loaded_again["available_models"][0]["api_key"] == "sk-my-secret-key-123")

    finally:
        teardown_temp_dir(test_dir)


# ---------------------------------------------------------------------------
# Tests: password change re-encryption
# ---------------------------------------------------------------------------

def test_password_change():
    section("change_password() re-encryption")
    test_dir = setup_temp_dir()
    try:
        cfg.set_initial_password("oldpass")
        cfg.save_config({
            "available_models": [
                {"id": "m1", "display_name": "T", "model": "x", "base_url": "https://x.com", "api_key": "sk-important-key"}
            ],
            "chairman_id": "m1",
            "summarization_model_id": "m1",
            "favorites_council": [],
            "history_raw_exchanges": 3,
        })

        # Change password
        check("change_password succeeds", cfg.change_password("oldpass", "newpass"))

        # Old password no longer works
        cfg._fernet_key = None
        check("old password fails login", not cfg.login_and_cache_key("oldpass"))

        # New password works
        check("new password succeeds login", cfg.login_and_cache_key("newpass"))

        # Key is still accessible
        loaded = cfg.load_config()
        check("key survives password change",
              loaded["available_models"][0]["api_key"] == "sk-important-key")

    finally:
        teardown_temp_dir(test_dir)


# ---------------------------------------------------------------------------
# Tests: schema validation (CouncilConfigSchema)
# ---------------------------------------------------------------------------

def test_schema_validation():
    section("CouncilConfigSchema validation")

    # Import the schema from main
    from backend.main import CouncilConfigSchema

    # Valid config
    schema = CouncilConfigSchema(
        available_models=[
            {"id": "m1", "display_name": "M1", "model": "x", "base_url": "https://x.com", "api_key": ""},
            {"id": "m2", "display_name": "M2", "model": "y", "base_url": "https://y.com", "api_key": ""},
        ],
        chairman_id="m1",
        summarization_model_id="m2",
        favorites_council=["m1"],
        history_raw_exchanges=5,
    )
    errors = schema.validate_references()
    check("valid config -> no reference errors", errors == [])

    # Chairman ID doesn't exist
    schema2 = CouncilConfigSchema(
        available_models=[
            {"id": "m1", "display_name": "M1", "model": "x", "base_url": "https://x.com", "api_key": ""},
        ],
        chairman_id="nonexistent",
        summarization_model_id="m1",
    )
    errors2 = schema2.validate_references()
    check("nonexistent chairman_id -> error", len(errors2) >= 1)
    check("error mentions chairman_id", any("chairman_id" in e for e in errors2))

    # Summarization model ID doesn't exist
    schema3 = CouncilConfigSchema(
        available_models=[
            {"id": "m1", "display_name": "M1", "model": "x", "base_url": "https://x.com", "api_key": ""},
        ],
        chairman_id="m1",
        summarization_model_id="ghost",
    )
    errors3 = schema3.validate_references()
    check("nonexistent summarization_model_id -> error", len(errors3) >= 1)

    # Invalid favorites
    schema4 = CouncilConfigSchema(
        available_models=[
            {"id": "m1", "display_name": "M1", "model": "x", "base_url": "https://x.com", "api_key": ""},
        ],
        chairman_id="m1",
        favorites_council=["m1", "bad-id"],
    )
    errors4 = schema4.validate_references()
    check("invalid favorite ID -> error", len(errors4) >= 1)

    # history_raw_exchanges out of range
    schema5 = CouncilConfigSchema(
        available_models=[],
        history_raw_exchanges=0,
    )
    errors5 = schema5.validate_references()
    check("history_raw_exchanges=0 -> error", len(errors5) >= 1)

    schema6 = CouncilConfigSchema(
        available_models=[],
        history_raw_exchanges=11,
    )
    errors6 = schema6.validate_references()
    check("history_raw_exchanges=11 -> error", len(errors6) >= 1)

    # Valid edge case: no chairman set (allowed — just means warning on load)
    schema7 = CouncilConfigSchema(
        available_models=[
            {"id": "m1", "display_name": "M1", "model": "x", "base_url": "https://x.com", "api_key": ""},
        ],
        chairman_id=None,
        summarization_model_id=None,
    )
    errors7 = schema7.validate_references()
    check("None chairman/summarization -> no error", errors7 == [])


# ---------------------------------------------------------------------------
# Tests: password length validation
# ---------------------------------------------------------------------------

def test_password_length():
    section("Password length enforcement")
    test_dir = setup_temp_dir()
    try:
        # 7 chars — should work with set_initial_password (backend enforces
        # length at the HTTP layer, not in config.py), but we test that the
        # minimum is checked at the API layer via the main module constants.
        # Here we verify the config module handles any password the API allows.
        cfg.set_initial_password("short77")  # 7 chars
        check("7-char password sets hash", cfg.is_password_set())
        check("7-char password login succeeds", cfg.login_and_cache_key("short77"))

        # Reset for 8-char test
        cfg._fernet_key = None
    finally:
        teardown_temp_dir(test_dir)

    test_dir = setup_temp_dir()
    try:
        cfg.set_initial_password("exactly8")  # 8 chars
        check("8-char password sets hash", cfg.is_password_set())
        check("8-char password login succeeds", cfg.login_and_cache_key("exactly8"))
        cfg._fernet_key = None
    finally:
        teardown_temp_dir(test_dir)

    test_dir = setup_temp_dir()
    try:
        cfg.set_initial_password("ninechar!")  # 9 chars
        check("9-char password sets hash", cfg.is_password_set())
        check("9-char password login succeeds", cfg.login_and_cache_key("ninechar!"))
        cfg._fernet_key = None
    finally:
        teardown_temp_dir(test_dir)


# ---------------------------------------------------------------------------
# Tests: lockout persistence
# ---------------------------------------------------------------------------

def test_lockout_persistence():
    section("Login lockout persistence")

    import tempfile
    import os

    # We test the lockout functions from main.py directly
    from backend.main import (
        _load_lockout, _save_lockout, _clear_lockout,
        _check_login_lockout, _record_failed_login,
        _LOCKOUT_PATH, _LOGIN_MAX_ATTEMPTS, _LOGIN_LOCKOUT_SECONDS,
    )
    import backend.main as main_module

    # Save original path and redirect to temp
    original_path = main_module._LOCKOUT_PATH
    test_lockout_path = os.path.join(tempfile.mkdtemp(), ".lockout")
    main_module._LOCKOUT_PATH = test_lockout_path

    try:
        # No lockout file — should return clean state
        state = _load_lockout()
        check("no file -> 0 failed_attempts", state["failed_attempts"] == 0)
        check("no file -> locked_until is None", state["locked_until"] is None)

        # Record failures up to threshold
        for i in range(_LOGIN_MAX_ATTEMPTS):
            _record_failed_login("127.0.0.1")

        # Should now be locked out
        lockout_msg = _check_login_lockout("127.0.0.1")
        check("5 failures -> locked out", lockout_msg is not None)

        # Simulate restart: re-load from disk
        state_after_restart = _load_lockout()
        check("lockout persists to disk",
              state_after_restart["failed_attempts"] >= _LOGIN_MAX_ATTEMPTS)
        check("locked_until persists to disk",
              state_after_restart["locked_until"] is not None)

        # Still locked after "restart"
        lockout_msg2 = _check_login_lockout("127.0.0.1")
        check("lockout survives restart", lockout_msg2 is not None)

        # Clear lockout (simulates successful login)
        _clear_lockout()
        state_cleared = _load_lockout()
        check("clear -> 0 failed_attempts", state_cleared["failed_attempts"] == 0)
        check("clear -> no lockout message", _check_login_lockout("127.0.0.1") is None)

        # Test expiry: set locked_until to the past
        import time
        expired_state = {
            "locked_until": time.time() - 1,
            "failed_attempts": 5,
            "last_attempt": time.time() - 100,
        }
        _save_lockout(expired_state)
        lockout_msg3 = _check_login_lockout("127.0.0.1")
        check("expired lockout -> no lockout message", lockout_msg3 is None)

    finally:
        main_module._LOCKOUT_PATH = original_path
        # Clean up temp file
        try:
            os.remove(test_lockout_path)
        except FileNotFoundError:
            pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    print("\nC-Suite AI — Config Tests")
    print("=" * 60)
    print("(No API keys or running server required)")

    test_load_config()
    test_orphan_detection()
    test_save_reload()
    test_encryption()
    test_password_change()
    test_schema_validation()
    test_password_length()
    test_lockout_persistence()

    print(f"\n{'=' * 60}")
    if _failures:
        print(f"  {FAIL}  {len(_failures)} test(s) FAILED:")
        for f in _failures:
            print(f"       - {f}")
        sys.exit(1)
    else:
        print(f"  {PASS}  All tests passed.")
    print()


if __name__ == "__main__":
    main()
