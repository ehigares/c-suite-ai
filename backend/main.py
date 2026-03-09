"""FastAPI backend for LLM Council."""

import asyncio
import json
import os
import re
import time
import uuid
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from . import storage
from .client import check_endpoint_health
from .config import (
    load_config,
    save_config,
    get_chairman,
    get_models_by_ids,
    get_summarization_model,
    is_password_set,
    set_initial_password,
    change_password,
    login_and_cache_key,
    create_session_token,
    validate_session_token,
)
from .council import (
    run_full_council,
    generate_conversation_title,
    stage1_collect_responses,
    stage2_collect_rankings,
    stage3_synthesize_final,
    calculate_aggregate_rankings,
    run_background_summarization,
)


# ---------------------------------------------------------------------------
# CORS and bind address — both derived from ALLOWED_ORIGINS env var
# ---------------------------------------------------------------------------

_DEFAULT_ORIGINS = "http://localhost:5173,http://localhost:3000"
_allowed_origins_str = os.environ.get("ALLOWED_ORIGINS", _DEFAULT_ORIGINS)
ALLOWED_ORIGINS = [o.strip() for o in _allowed_origins_str.split(",") if o.strip()]

# Derive bind host: if any origin is non-localhost, bind to 0.0.0.0 so
# LAN clients can reach us. Otherwise bind to 127.0.0.1 (most secure).
_LOCALHOST_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _derive_bind_host(origins: List[str]) -> str:
    for origin in origins:
        try:
            host = urlparse(origin).hostname or ""
        except Exception:
            continue
        if host and host not in _LOCALHOST_HOSTS:
            return "0.0.0.0"
    return "127.0.0.1"


BIND_HOST = _derive_bind_host(ALLOWED_ORIGINS)


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="LLM Council API")
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please wait a moment and try again."},
    )


# CORS origins driven by ALLOWED_ORIGINS env var (default: localhost only)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Login lockout tracking (persisted to data/.lockout)
# ---------------------------------------------------------------------------

_LOGIN_MAX_ATTEMPTS = 5
_LOGIN_LOCKOUT_SECONDS = 15 * 60  # 15 minutes
_LOCKOUT_PATH = os.path.join("data", ".lockout")


def _load_lockout() -> dict:
    """Load lockout state from disk. Returns defaults if file doesn't exist."""
    try:
        with open(_LOCKOUT_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {"locked_until": None, "failed_attempts": 0, "last_attempt": None}


def _save_lockout(state: dict):
    """Write lockout state to disk atomically (temp file + rename)."""
    os.makedirs("data", exist_ok=True)
    tmp_path = _LOCKOUT_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(state, f)
    os.replace(tmp_path, _LOCKOUT_PATH)


def _clear_lockout():
    """Remove lockout state from both memory and disk."""
    try:
        os.remove(_LOCKOUT_PATH)
    except FileNotFoundError:
        pass


def _check_login_lockout(ip: str) -> Optional[str]:
    """Return an error message if locked out, else None."""
    state = _load_lockout()
    now = time.time()

    locked_until = state.get("locked_until")
    if locked_until is not None:
        if now < locked_until:
            remaining = int(locked_until - now)
            minutes = max(1, remaining // 60)
            return f"Too many failed login attempts. Try again in {minutes} minute(s)."
        else:
            # Lockout has expired — clear it
            _clear_lockout()
    return None


def _record_failed_login(ip: str):
    """Record a failed login attempt. Sets lockout if threshold reached."""
    state = _load_lockout()
    now = time.time()

    state["failed_attempts"] = state.get("failed_attempts", 0) + 1
    state["last_attempt"] = now

    if state["failed_attempts"] >= _LOGIN_MAX_ATTEMPTS:
        state["locked_until"] = now + _LOGIN_LOCKOUT_SECONDS

    _save_lockout(state)


# ---------------------------------------------------------------------------
# Auth middleware — protect all endpoints except public ones
# ---------------------------------------------------------------------------

# Paths that don't require authentication
_PUBLIC_PATHS = {
    "/",
    "/api/login",
    "/api/health",
    "/api/auth/status",
}


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Require a valid JWT for all endpoints except public ones."""
    path = request.url.path

    # Allow public endpoints through
    if path in _PUBLIC_PATHS:
        return await call_next(request)

    # Allow OPTIONS (CORS preflight) through
    if request.method == "OPTIONS":
        return await call_next(request)

    # If no password is set yet, allow everything (first-run setup)
    if not is_password_set():
        return await call_next(request)

    # Check for Authorization header
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required. Please log in."},
        )

    token = auth_header[7:]  # Strip "Bearer "
    if not validate_session_token(token):
        return JSONResponse(
            status_code=401,
            content={"detail": "Session expired. Please log in again."},
        )

    return await call_next(request)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class CreateConversationRequest(BaseModel):
    """Request to create a new conversation, including the locked council config."""
    council_model_ids: List[str]   # UUIDs of models selected for this conversation


class SendMessageRequest(BaseModel):
    """Request to send a message in a conversation."""
    content: str


class ConversationMetadata(BaseModel):
    """Conversation metadata for list view."""
    id: str
    created_at: str
    title: str
    message_count: int


class Conversation(BaseModel):
    """Full conversation with all messages."""
    id: str
    created_at: str
    title: str
    messages: List[Dict[str, Any]]
    council_config: Optional[Dict[str, Any]] = None


class TestConnectionRequest(BaseModel):
    """Request to test connectivity for a single model config."""
    model: str
    base_url: str
    api_key: str = ""
    display_name: str = ""


class ModelConfigSchema(BaseModel):
    """Schema for a single model in the config."""
    id: str
    display_name: str
    model: str
    base_url: str
    api_key: str = ""


class CouncilConfigSchema(BaseModel):
    """
    Full schema for council_config.json with cross-field validation.
    Used by POST /api/config to validate before writing to disk.
    """
    available_models: List[ModelConfigSchema]
    chairman_id: Optional[str] = None
    summarization_model_id: Optional[str] = None
    favorites_council: List[str] = []
    history_raw_exchanges: int = 3

    def validate_references(self) -> List[str]:
        """Check that all ID references point to models that exist in the pool."""
        errors = []
        valid_ids = {m.id for m in self.available_models}

        if self.chairman_id and self.chairman_id not in valid_ids:
            errors.append(f"chairman_id '{self.chairman_id}' does not match any model in available_models")

        if self.summarization_model_id and self.summarization_model_id not in valid_ids:
            errors.append(f"summarization_model_id '{self.summarization_model_id}' does not match any model in available_models")

        invalid_favs = [fid for fid in self.favorites_council if fid not in valid_ids]
        if invalid_favs:
            errors.append(f"favorites_council contains IDs not in available_models: {invalid_favs}")

        if not 1 <= self.history_raw_exchanges <= 10:
            errors.append(f"history_raw_exchanges must be between 1 and 10 (got {self.history_raw_exchanges})")

        return errors


class SaveConfigRequest(BaseModel):
    """Request body for POST /api/config."""
    config: Dict[str, Any]


class LoginRequest(BaseModel):
    """Request body for POST /api/login."""
    password: str


class SetPasswordRequest(BaseModel):
    """Request body for initial password setup."""
    password: str


class ChangePasswordRequest(BaseModel):
    """Request body for password change."""
    old_password: str
    new_password: str


# ---------------------------------------------------------------------------
# Input validation helpers
# ---------------------------------------------------------------------------

_URL_PATTERN = re.compile(r'^https?://.+')


def _validate_model_config(model: Dict[str, Any]) -> List[str]:
    """
    Validate a model config dict. Returns a list of error messages (empty = valid).
    """
    errors = []

    base_url = model.get("base_url", "")
    if base_url and not _URL_PATTERN.match(base_url.strip()):
        errors.append(f"base_url must be a valid http:// or https:// URL (got: {base_url[:50]})")

    api_key = model.get("api_key", "")
    if len(api_key) > 200:
        errors.append("api_key must be 200 characters or fewer")

    display_name = model.get("display_name", "")
    if len(display_name) > 50:
        errors.append("display_name must be 50 characters or fewer")
    # Strip HTML tags from display_name
    if display_name and re.search(r'<[^>]+>', display_name):
        errors.append("display_name must not contain HTML tags")

    model_id = model.get("model", "")
    if len(model_id) > 100:
        errors.append("model must be 100 characters or fewer")

    return errors


def _sanitize_model_config(model: Dict[str, Any]) -> Dict[str, Any]:
    """Strip whitespace from model config fields."""
    sanitized = dict(model)
    for field in ("api_key", "model", "base_url"):
        if field in sanitized and isinstance(sanitized[field], str):
            sanitized[field] = sanitized[field].strip()
    if "display_name" in sanitized and isinstance(sanitized["display_name"], str):
        sanitized["display_name"] = sanitized["display_name"].strip()
        # Strip HTML tags
        sanitized["display_name"] = re.sub(r'<[^>]+>', '', sanitized["display_name"])
    return sanitized


# ---------------------------------------------------------------------------
# Health & Auth endpoints
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "LLM Council API"}


@app.get("/api/health")
async def health():
    """Explicit health check — used by start.sh polling."""
    return {"status": "ok"}


@app.get("/api/auth/status")
async def auth_status():
    """Return whether a password has been set (for frontend login/setup flow)."""
    return {"password_set": is_password_set()}


@app.post("/api/login")
@limiter.limit("5/minute")
async def login(request: Request, body: LoginRequest):
    """
    Authenticate with password and receive a session token.
    Rate limited to 5 attempts per minute. Locked out after 5 failures for 15 minutes.
    """
    ip = get_remote_address(request)

    # Check lockout
    lockout_msg = _check_login_lockout(ip)
    if lockout_msg:
        raise HTTPException(status_code=429, detail=lockout_msg)

    if not is_password_set():
        raise HTTPException(status_code=400, detail="No password set. Please complete first-run setup.")

    if not login_and_cache_key(body.password):
        _record_failed_login(ip)
        raise HTTPException(status_code=401, detail="Incorrect password.")

    # Clear lockout on successful login
    _clear_lockout()

    token = create_session_token()
    # Flag if existing password is shorter than current minimum (8 chars)
    password_too_short = len(body.password) < 8
    return {"token": token, "password_too_short": password_too_short}


@app.post("/api/setup-password")
async def setup_password(body: SetPasswordRequest):
    """
    Set the initial password during first-run setup.
    Only works if no password has been set yet.
    """
    if is_password_set():
        raise HTTPException(status_code=400, detail="Password already set. Use the change password flow.")

    if len(body.password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters.")

    set_initial_password(body.password)
    token = create_session_token()
    return {"token": token}


@app.post("/api/change-password")
async def change_password_endpoint(body: ChangePasswordRequest):
    """Change the password. Re-encrypts all stored API keys."""
    if len(body.new_password) < 8:
        raise HTTPException(status_code=422, detail="New password must be at least 8 characters.")

    if not change_password(body.old_password, body.new_password):
        raise HTTPException(status_code=401, detail="Current password is incorrect.")

    token = create_session_token()
    return {"token": token, "message": "Password changed successfully."}


# ---------------------------------------------------------------------------
# Config endpoints
# ---------------------------------------------------------------------------

def _mask_api_keys(config: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of the config with API keys masked for safe frontend delivery."""
    import copy
    masked = copy.deepcopy(config)
    for model in masked.get("available_models", []):
        key = model.get("api_key", "")
        if key:
            # Show only first 8 chars so users can verify which key is set
            model["api_key"] = key[:8] + "..." if len(key) > 8 else "***"
    # Strip internal keys
    masked.pop("_warnings", None)
    # Never send the password hash to the frontend
    masked.pop("password_hash", None)
    return masked


def _strip_council_keys(conversation: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return a copy of a conversation dict with API keys fully removed from
    the locked council_config snapshot.

    The frontend only needs display_name and base_url (for source badges).
    It never needs any part of the real API key, so we blank them entirely.
    Applied to every endpoint that returns a full conversation object.
    """
    import copy
    conv = copy.deepcopy(conversation)
    for m in conv.get("council_config", {}).get("available_models", []):
        m["api_key"] = ""
    return conv


@app.get("/api/config")
async def get_config():
    """Return the current council config with API keys masked."""
    config = load_config()
    return {
        "config": _mask_api_keys(config),
        "warnings": config.get("_warnings", []),
    }


@app.post("/api/config")
@limiter.limit("20/minute")
async def post_config(request: Request, body: SaveConfigRequest):
    """Save an updated council config to disk. Validates schema and model fields."""
    config = body.config

    # Structural validation via Pydantic schema
    try:
        schema = CouncilConfigSchema(**config)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid config structure: {e}")

    # Cross-field reference validation
    ref_errors = schema.validate_references()
    if ref_errors:
        raise HTTPException(status_code=422, detail="; ".join(ref_errors))

    # Per-model field validation (URL format, lengths, HTML)
    for model in config.get("available_models", []):
        errors = _validate_model_config(model)
        if errors:
            raise HTTPException(status_code=422, detail="; ".join(errors))
        # Sanitize fields
        model.update(_sanitize_model_config(model))

    save_config(config)
    loaded = load_config()
    return {
        "config": _mask_api_keys(loaded),
        "warnings": loaded.get("_warnings", []),
    }


@app.post("/api/test-connection")
@limiter.limit("20/minute")
async def test_connection(request: Request, body: TestConnectionRequest):
    """
    Test connectivity for a single model configuration.
    Returns whether the endpoint is alive and the model is loaded.
    """
    # Validate fields
    test_model = {
        "model": body.model,
        "base_url": body.base_url,
        "api_key": body.api_key,
        "display_name": body.display_name,
    }
    errors = _validate_model_config(test_model)
    if errors:
        raise HTTPException(status_code=422, detail="; ".join(errors))

    model_config = {
        "id": "test",
        "model": body.model.strip(),
        "base_url": body.base_url.strip(),
        "api_key": body.api_key.strip(),
        "display_name": body.display_name or body.model,
    }
    result = await check_endpoint_health(model_config)
    return result


@app.post("/api/wakeup")
@limiter.limit("10/minute")
async def wakeup(request: Request, body: Dict[str, Any] = {}):
    """
    Trigger a warm-up ping on all RunPod endpoints in the given council.

    Expects JSON body: { "council_model_ids": ["uuid", ...] }
    Returns per-model health status.
    """
    config = load_config()
    ids = body.get("council_model_ids", [])
    models = get_models_by_ids(config, ids)

    # Filter to RunPod endpoints only
    runpod_models = [m for m in models if "proxy.runpod.net" in m.get("base_url", "")]

    if not runpod_models:
        return {"status": "no_runpod_endpoints", "results": []}

    tasks = [check_endpoint_health(m) for m in runpod_models]
    results = await asyncio.gather(*tasks)

    return {
        "status": "checked",
        "results": [
            {
                "model_id": m["id"],
                "display_name": m["display_name"],
                **result,
            }
            for m, result in zip(runpod_models, results)
        ],
    }


@app.get("/api/endpoint-status")
async def endpoint_status(council_model_ids: str = ""):
    """
    Check the status of RunPod endpoints in a given council.

    Pass model IDs as a comma-separated query parameter:
        GET /api/endpoint-status?council_model_ids=uuid1,uuid2
    """
    config = load_config()
    ids = [i.strip() for i in council_model_ids.split(",") if i.strip()]
    models = get_models_by_ids(config, ids)

    runpod_models = [m for m in models if "proxy.runpod.net" in m.get("base_url", "")]

    if not runpod_models:
        return {"status": "no_runpod_endpoints", "results": []}

    tasks = [check_endpoint_health(m) for m in runpod_models]
    results = await asyncio.gather(*tasks)

    return {
        "status": "checked",
        "results": [
            {
                "model_id": m["id"],
                "display_name": m["display_name"],
                **result,
            }
            for m, result in zip(runpod_models, results)
        ],
    }


# ---------------------------------------------------------------------------
# Conversation endpoints
# ---------------------------------------------------------------------------

_MAX_MESSAGE_LENGTH = 32_000

@app.get("/api/conversations", response_model=List[ConversationMetadata])
async def list_conversations():
    """List all conversations (metadata only)."""
    return storage.list_conversations()


@app.post("/api/conversations", response_model=Conversation)
@limiter.limit("20/minute")
async def create_conversation(request: Request, body: CreateConversationRequest):
    """
    Create a new conversation with a locked council configuration.

    The selected council models are snapshotted from the current config
    and stored with the conversation so it always uses the original models.
    """
    config = load_config()

    # Snapshot the selected models at conversation creation time
    selected_models = get_models_by_ids(config, body.council_model_ids)
    if not selected_models:
        raise HTTPException(status_code=400, detail="No valid council models selected.")

    chairman = get_chairman(config)
    if chairman is None:
        raise HTTPException(status_code=400, detail="No chairman model configured. Please set one in Settings.")

    # Build the locked council snapshot stored with the conversation
    council_snapshot = {
        "available_models": selected_models,
        "chairman_id": config.get("chairman_id"),
        "council_model_ids": body.council_model_ids,
    }

    conversation_id = str(uuid.uuid4())
    conversation = storage.create_conversation(conversation_id, council_snapshot)
    return _strip_council_keys(conversation)


@app.get("/api/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: str):
    """Get a specific conversation with all its messages."""
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return _strip_council_keys(conversation)


@app.post("/api/conversations/{conversation_id}/message")
@limiter.limit("10/minute")
async def send_message(request: Request, conversation_id: str, body: SendMessageRequest):
    """
    Send a message and run the 3-stage council process.
    Returns the complete response with all stages.
    """
    # Message size limit
    if len(body.content) > _MAX_MESSAGE_LENGTH:
        raise HTTPException(
            status_code=413,
            detail=f"Message too long. Maximum length is {_MAX_MESSAGE_LENGTH:,} characters.",
        )

    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    is_first_message = len(conversation["messages"]) == 0
    storage.add_user_message(conversation_id, body.content)

    council_config = conversation.get("council_config", {})

    # Load global config to get user's raw-exchanges setting
    global_config = load_config()
    raw_exchanges = global_config.get("history_raw_exchanges", 3)

    # Build history for this request (summary + recent raw exchanges)
    history = storage.build_history(conversation, raw_exchanges)

    if is_first_message:
        chairman = get_chairman(council_config)
        if chairman:
            title = await generate_conversation_title(body.content, chairman)
        else:
            title = "New Conversation"
        storage.update_conversation_title(conversation_id, title)

    stage1_results, stage2_results, stage3_result, metadata = await run_full_council(
        body.content, council_config, history
    )

    storage.add_assistant_message(conversation_id, stage1_results, stage2_results, stage3_result)

    # Trigger background summarization every 5 exchanges (non-blocking)
    updated_conv = storage.get_conversation(conversation_id)
    exchange_count = storage.count_exchanges(updated_conv)
    summ_model = get_summarization_model(global_config)
    if summ_model and exchange_count > 0 and exchange_count % 5 == 0:
        asyncio.create_task(
            run_background_summarization(conversation_id, updated_conv, summ_model, raw_exchanges)
        )

    return {
        "stage1": stage1_results,
        "stage2": stage2_results,
        "stage3": stage3_result,
        "metadata": metadata,
    }


@app.post("/api/conversations/{conversation_id}/message/stream")
@limiter.limit("10/minute")
async def send_message_stream(request: Request, conversation_id: str, body: SendMessageRequest):
    """
    Send a message and stream the 3-stage council process via Server-Sent Events.
    Each stage completion is sent as a separate SSE event.
    """
    # Message size limit
    if len(body.content) > _MAX_MESSAGE_LENGTH:
        raise HTTPException(
            status_code=413,
            detail=f"Message too long. Maximum length is {_MAX_MESSAGE_LENGTH:,} characters.",
        )

    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    is_first_message = len(conversation["messages"]) == 0
    council_config = conversation.get("council_config", {})

    # Load global config once — used for history window and summarization model
    global_config = load_config()
    raw_exchanges = global_config.get("history_raw_exchanges", 3)

    async def event_generator():
        try:
            storage.add_user_message(conversation_id, body.content)

            # Build history before running stages, using user's configured window size
            conv = storage.get_conversation(conversation_id)
            history = storage.build_history(conv, raw_exchanges)

            from .config import get_models_by_ids
            council_model_ids = council_config.get("council_model_ids", [])
            council_models = get_models_by_ids(council_config, council_model_ids)
            chairman = get_chairman(council_config)

            # Start title generation in background on first message
            title_task = None
            if is_first_message and chairman:
                title_task = asyncio.create_task(
                    generate_conversation_title(body.content, chairman)
                )

            # Stage 1
            yield f"data: {json.dumps({'type': 'stage1_start'})}\n\n"
            stage1_results = await stage1_collect_responses(
                body.content, council_models, history
            )
            yield f"data: {json.dumps({'type': 'stage1_complete', 'data': stage1_results})}\n\n"

            # Stage 2
            yield f"data: {json.dumps({'type': 'stage2_start'})}\n\n"
            stage2_results, label_to_model = await stage2_collect_rankings(
                body.content, stage1_results, council_models, history
            )
            aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)
            yield f"data: {json.dumps({'type': 'stage2_complete', 'data': stage2_results, 'metadata': {'label_to_model': label_to_model, 'aggregate_rankings': aggregate_rankings}})}\n\n"

            # Stage 3
            yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"
            stage3_result = await stage3_synthesize_final(
                body.content, stage1_results, stage2_results, chairman, history
            )
            yield f"data: {json.dumps({'type': 'stage3_complete', 'data': stage3_result})}\n\n"

            # Title (if first message)
            if title_task:
                title = await title_task
                storage.update_conversation_title(conversation_id, title)
                yield f"data: {json.dumps({'type': 'title_complete', 'data': {'title': title}})}\n\n"

            # Persist the assistant message
            storage.add_assistant_message(
                conversation_id, stage1_results, stage2_results, stage3_result
            )

            # Trigger background summarization every 5 exchanges (non-blocking fire-and-forget)
            updated_conv = storage.get_conversation(conversation_id)
            exchange_count = storage.count_exchanges(updated_conv)
            summ_model = get_summarization_model(global_config)
            if summ_model and exchange_count > 0 and exchange_count % 5 == 0:
                asyncio.create_task(
                    run_background_summarization(conversation_id, updated_conv, summ_model, raw_exchanges)
                )

            yield f"data: {json.dumps({'type': 'complete'})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


if __name__ == "__main__":
    import uvicorn
    print(f"CORS origins: {ALLOWED_ORIGINS}")
    print(f"Binding to: {BIND_HOST}:8001")
    uvicorn.run(app, host=BIND_HOST, port=8001)
