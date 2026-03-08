"""FastAPI backend for LLM Council."""

import asyncio
import json
import uuid
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from . import storage
from .client import check_endpoint_health
from .config import load_config, save_config, get_chairman, get_models_by_ids, get_summarization_model
from .council import (
    run_full_council,
    generate_conversation_title,
    stage1_collect_responses,
    stage2_collect_rankings,
    stage3_synthesize_final,
    calculate_aggregate_rankings,
    run_background_summarization,
)

app = FastAPI(title="LLM Council API")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


class TestConnectionRequest(BaseModel):
    """Request to test connectivity for a single model config."""
    model: str
    base_url: str
    api_key: str = ""
    display_name: str = ""


class SaveConfigRequest(BaseModel):
    """Request body for POST /api/config."""
    config: Dict[str, Any]


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "LLM Council API"}


# ---------------------------------------------------------------------------
# Config endpoints (Sprint 2 — fully wired here so Settings UI can call them)
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
    return masked


@app.get("/api/config")
async def get_config():
    """Return the current council config with API keys masked."""
    config = load_config()
    return {
        "config": _mask_api_keys(config),
        "warnings": config.get("_warnings", []),
    }


@app.post("/api/config")
async def post_config(request: SaveConfigRequest):
    """Save an updated council config to disk."""
    # Never allow a client to overwrite API keys with masked values —
    # the frontend must send back the full original key or an empty string.
    save_config(request.config)
    config = load_config()
    return {
        "config": _mask_api_keys(config),
        "warnings": config.get("_warnings", []),
    }


@app.post("/api/test-connection")
async def test_connection(request: TestConnectionRequest):
    """
    Test connectivity for a single model configuration.
    Returns whether the endpoint is alive and the model is loaded.
    """
    model_config = {
        "id": "test",
        "model": request.model,
        "base_url": request.base_url,
        "api_key": request.api_key,
        "display_name": request.display_name or request.model,
    }
    result = await check_endpoint_health(model_config)
    return result


@app.post("/api/wakeup")
async def wakeup(body: Dict[str, Any] = {}):
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

@app.get("/api/conversations", response_model=List[ConversationMetadata])
async def list_conversations():
    """List all conversations (metadata only)."""
    return storage.list_conversations()


@app.post("/api/conversations", response_model=Conversation)
async def create_conversation(request: CreateConversationRequest):
    """
    Create a new conversation with a locked council configuration.

    The selected council models are snapshotted from the current config
    and stored with the conversation so it always uses the original models.
    """
    config = load_config()

    # Snapshot the selected models at conversation creation time
    selected_models = get_models_by_ids(config, request.council_model_ids)
    if not selected_models:
        raise HTTPException(status_code=400, detail="No valid council models selected.")

    chairman = get_chairman(config)
    if chairman is None:
        raise HTTPException(status_code=400, detail="No chairman model configured. Please set one in Settings.")

    # Build the locked council snapshot stored with the conversation
    council_snapshot = {
        "available_models": selected_models,
        "chairman_id": config.get("chairman_id"),
        "council_model_ids": request.council_model_ids,
    }

    conversation_id = str(uuid.uuid4())
    conversation = storage.create_conversation(conversation_id, council_snapshot)
    return conversation


@app.get("/api/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: str):
    """Get a specific conversation with all its messages."""
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@app.post("/api/conversations/{conversation_id}/message")
async def send_message(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and run the 3-stage council process.
    Returns the complete response with all stages.
    """
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    is_first_message = len(conversation["messages"]) == 0
    storage.add_user_message(conversation_id, request.content)

    council_config = conversation.get("council_config", {})

    # Load global config to get user's raw-exchanges setting
    global_config = load_config()
    raw_exchanges = global_config.get("history_raw_exchanges", 3)

    # Build history for this request (summary + recent raw exchanges)
    history = storage.build_history(conversation, raw_exchanges)

    if is_first_message:
        chairman = get_chairman(council_config)
        if chairman:
            title = await generate_conversation_title(request.content, chairman)
        else:
            title = "New Conversation"
        storage.update_conversation_title(conversation_id, title)

    stage1_results, stage2_results, stage3_result, metadata = await run_full_council(
        request.content, council_config, history
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
async def send_message_stream(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and stream the 3-stage council process via Server-Sent Events.
    Each stage completion is sent as a separate SSE event.
    """
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
            storage.add_user_message(conversation_id, request.content)

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
                    generate_conversation_title(request.content, chairman)
                )

            # Stage 1
            yield f"data: {json.dumps({'type': 'stage1_start'})}\n\n"
            stage1_results = await stage1_collect_responses(
                request.content, council_models, history
            )
            yield f"data: {json.dumps({'type': 'stage1_complete', 'data': stage1_results})}\n\n"

            # Stage 2
            yield f"data: {json.dumps({'type': 'stage2_start'})}\n\n"
            stage2_results, label_to_model = await stage2_collect_rankings(
                request.content, stage1_results, council_models, history
            )
            aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)
            yield f"data: {json.dumps({'type': 'stage2_complete', 'data': stage2_results, 'metadata': {'label_to_model': label_to_model, 'aggregate_rankings': aggregate_rankings}})}\n\n"

            # Stage 3
            yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"
            stage3_result = await stage3_synthesize_final(
                request.content, stage1_results, stage2_results, chairman, history
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
    uvicorn.run(app, host="0.0.0.0", port=8001)
