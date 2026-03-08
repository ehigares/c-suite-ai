"""JSON-based storage for conversations.

Schema for each conversation file:
{
    "id": "uuid",
    "created_at": "ISO timestamp",
    "title": "...",
    "council_config": { ...locked snapshot... },
    "running_summary": "...",
    "summary_last_updated_at_exchange": 0,
    "messages": [
        {"role": "user", "content": "..."},
        {"role": "assistant", "stage1": [...], "stage2": [...], "stage3": {...}}
    ]
}

One exchange = one user message + one assistant message (Stage 1/2 debate is internal).
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
from .config import DATA_DIR


def ensure_data_dir():
    """Ensure the conversations directory exists."""
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)


def get_conversation_path(conversation_id: str) -> str:
    """Get the file path for a conversation."""
    return os.path.join(DATA_DIR, f"{conversation_id}.json")


def create_conversation(
    conversation_id: str,
    council_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a new conversation with a locked council snapshot.

    Args:
        conversation_id: Unique identifier for the conversation
        council_config: The locked council snapshot (models + chairman at creation time)

    Returns:
        New conversation dict
    """
    ensure_data_dir()

    conversation = {
        "id": conversation_id,
        "created_at": datetime.utcnow().isoformat(),
        "title": "New Conversation",
        "council_config": council_config or {},
        "running_summary": "",
        "summary_last_updated_at_exchange": 0,
        "messages": [],
    }

    path = get_conversation_path(conversation_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(conversation, f, indent=2)

    return conversation


def get_conversation(conversation_id: str) -> Optional[Dict[str, Any]]:
    """
    Load a conversation from storage.

    Returns None if the conversation file doesn't exist.
    """
    path = get_conversation_path(conversation_id)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_conversation(conversation: Dict[str, Any]):
    """Save a conversation dict to its JSON file."""
    ensure_data_dir()
    path = get_conversation_path(conversation["id"])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(conversation, f, indent=2)


def list_conversations() -> List[Dict[str, Any]]:
    """
    List all conversations (metadata only, newest first).
    """
    ensure_data_dir()

    conversations = []
    for filename in os.listdir(DATA_DIR):
        if not filename.endswith(".json"):
            continue
        path = os.path.join(DATA_DIR, filename)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            conversations.append({
                "id": data["id"],
                "created_at": data["created_at"],
                "title": data.get("title", "New Conversation"),
                "message_count": len(data["messages"]),
            })
        except (json.JSONDecodeError, KeyError):
            # Skip corrupted files rather than crashing the whole list
            continue

    conversations.sort(key=lambda x: x["created_at"], reverse=True)
    return conversations


def add_user_message(conversation_id: str, content: str):
    """Append a user message to the conversation."""
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    conversation["messages"].append({
        "role": "user",
        "content": content,
    })

    save_conversation(conversation)


def add_assistant_message(
    conversation_id: str,
    stage1: List[Dict[str, Any]],
    stage2: List[Dict[str, Any]],
    stage3: Dict[str, Any],
):
    """
    Append an assistant message (with all 3 stages) to the conversation.

    Only the Chairman's Stage 3 answer counts as the "exchange" for history
    purposes — Stage 1 and Stage 2 are internal scaffolding.
    """
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    conversation["messages"].append({
        "role": "assistant",
        "stage1": stage1,
        "stage2": stage2,
        "stage3": stage3,
    })

    save_conversation(conversation)


def update_conversation_title(conversation_id: str, title: str):
    """Update the title of a conversation."""
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")
    conversation["title"] = title
    save_conversation(conversation)


def update_running_summary(
    conversation_id: str,
    summary: str,
    updated_at_exchange: int,
):
    """
    Store an updated running summary after background summarization completes.

    Args:
        conversation_id: Conversation identifier
        summary: The new compressed summary text
        updated_at_exchange: The exchange number at which this summary was generated
    """
    conversation = get_conversation(conversation_id)
    if conversation is None:
        return  # Conversation may have been deleted — fail silently
    conversation["running_summary"] = summary
    conversation["summary_last_updated_at_exchange"] = updated_at_exchange
    save_conversation(conversation)


def count_exchanges(conversation: Dict[str, Any]) -> int:
    """
    Count the number of complete exchanges (user + chairman pairs) in a conversation.

    Stage 1/2 debate content is not counted — only user + assistant message pairs.
    """
    messages = conversation.get("messages", [])
    return sum(1 for m in messages if m.get("role") == "assistant")


def build_history(
    conversation: Dict[str, Any],
    raw_exchanges: int = 3,
) -> Optional[Dict[str, Any]]:
    """
    Build the history dict to pass to council stages.

    Extracts the running summary plus the last N raw exchanges
    (user question + Chairman answer only).

    Args:
        conversation: Full conversation dict
        raw_exchanges: How many recent exchanges to include in full

    Returns:
        History dict with 'running_summary' and 'recent_exchanges',
        or None if no history exists yet.
    """
    messages = conversation.get("messages", [])
    running_summary = conversation.get("running_summary", "")

    # Pair up user + assistant messages into exchanges
    exchanges = []
    i = 0
    while i < len(messages) - 1:
        if messages[i].get("role") == "user" and messages[i + 1].get("role") == "assistant":
            chairman_response = messages[i + 1].get("stage3", {}).get("response", "")
            exchanges.append({
                "user": messages[i]["content"],
                "chairman": chairman_response,
            })
            i += 2
        else:
            i += 1

    # Take only the last N exchanges for the raw window
    recent = exchanges[-raw_exchanges:] if exchanges else []

    if not running_summary and not recent:
        return None

    return {
        "running_summary": running_summary,
        "recent_exchanges": recent,
    }
