"""API client for making LLM requests to any OpenAI-compatible endpoint.

Each model is configured independently with its own base_url and api_key,
so this client can talk to OpenRouter, RunPod/Ollama, local Ollama, or any
other OpenAI-compatible API interchangeably.
"""

import asyncio
import httpx
from typing import List, Dict, Any, Optional


async def query_model(
    model_config: Dict[str, Any],
    messages: List[Dict[str, str]],
    timeout: float = 120.0
) -> Optional[Dict[str, Any]]:
    """
    Query a single model using its config dict.

    Args:
        model_config: Dict with 'model', 'base_url', 'api_key', and 'display_name' keys
        messages: List of message dicts with 'role' and 'content'
        timeout: Request timeout in seconds

    Returns:
        Response dict with 'content' and optional 'reasoning_details', or None if failed
    """
    headers = {"Content-Type": "application/json"}

    # Only add Authorization header when api_key is non-empty.
    # An empty string must never become "Bearer " — that breaks some endpoints.
    api_key = model_config.get("api_key", "")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    # Build the chat completions URL from the model's base_url
    base_url = model_config["base_url"].rstrip("/")
    url = f"{base_url}/chat/completions"

    payload = {
        "model": model_config["model"],
        "messages": messages,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()

            data = response.json()
            message = data["choices"][0]["message"]

            return {
                "content": message.get("content"),
                "reasoning_details": message.get("reasoning_details"),
            }

    except Exception as e:
        display_name = model_config.get("display_name", model_config.get("model", "unknown"))
        print(f"Error querying model '{display_name}': {e}")
        return None


async def query_models_parallel(
    model_configs: List[Dict[str, Any]],
    messages: List[Dict[str, str]],
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Query multiple models in parallel.

    Args:
        model_configs: List of model config dicts (each with 'id', 'model', 'base_url', 'api_key')
        messages: List of message dicts to send to each model

    Returns:
        Dict mapping model UUID (config['id']) to response dict (or None if failed)
    """
    tasks = [query_model(config, messages) for config in model_configs]
    responses = await asyncio.gather(*tasks)
    return {config["id"]: response for config, response in zip(model_configs, responses)}


async def check_endpoint_health(
    model_config: Dict[str, Any],
    timeout: float = 30.0
) -> Dict[str, Any]:
    """
    Check if a model endpoint is alive by calling GET {base_url}/models,
    then verify authentication by making a minimal chat completion request.

    Args:
        model_config: Dict with 'model', 'base_url', 'api_key', 'display_name' keys
        timeout: Request timeout in seconds

    Returns:
        Dict with 'alive' (bool), 'model_loaded' (bool), 'auth_ok' (bool),
        and optional 'error' (str)
    """
    headers = {"Content-Type": "application/json"}
    api_key = model_config.get("api_key", "")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    base_url = model_config["base_url"].rstrip("/")
    url = f"{base_url}/models"

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()

            # Check if the configured model ID is in the response
            data = response.json()
            model_ids = [m.get("id", "") for m in data.get("data", [])]
            model_loaded = model_config["model"] in model_ids

            # Verify authentication with a minimal chat completion request
            # This catches cases where /models is public but the key is invalid
            auth_ok = True
            if api_key:
                auth_ok = await _verify_auth(client, base_url, headers, model_config["model"])

            return {
                "alive": True,
                "model_loaded": model_loaded,
                "auth_ok": auth_ok,
            }

    except Exception as e:
        return {"alive": False, "model_loaded": False, "auth_ok": False, "error": str(e)}


async def _verify_auth(
    client: httpx.AsyncClient,
    base_url: str,
    headers: Dict[str, str],
    model: str,
) -> bool:
    """
    Verify authentication by sending a minimal chat completion request.
    Returns True if the key is accepted (not 401/403), False otherwise.
    """
    url = f"{base_url}/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Hi"}],
        "max_tokens": 1,
    }
    try:
        response = await client.post(url, headers=headers, json=payload)
        if response.status_code in (401, 403):
            return False
        # Any other response (200, 400, 429, etc.) means the key was accepted
        return True
    except Exception:
        # Network errors don't indicate auth failure
        return True
