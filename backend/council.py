"""3-stage C-Suite AI council orchestration.

Accepts a council_config dict (the locked snapshot for this conversation)
rather than pulling from global constants — this is what allows each
conversation to use its own set of models.

History format expected in `history` parameter:
    {
        "running_summary": "...",          # compressed summary of older exchanges
        "recent_exchanges": [              # last N raw exchanges
            {"user": "...", "chairman": "..."},
            ...
        ]
    }
"""

from typing import List, Dict, Any, Tuple, Optional
from .client import query_models_parallel, query_model
from .config import get_chairman

# Hardcoded — not user-editable per spec
_SUMMARIZATION_PROMPT = (
    "You are maintaining a running summary of a multi-turn conversation for context. "
    "You will be given the current summary (if any) and a set of new exchanges to incorporate. "
    "Write an updated summary of 3–6 sentences covering: the user's overall goal, key decisions "
    "or conclusions reached, important constraints or preferences established, and any open "
    "questions still being worked on. Be factual, concise, and write in third person "
    "(e.g. \"The user is trying to...\"). Do not editorialize."
)


def _build_history_prefix(history: Optional[Dict[str, Any]]) -> str:
    """
    Build the history context string to prepend to each model's messages.

    Returns an empty string if there is no history to inject.
    """
    if not history:
        return ""

    parts = []

    summary = history.get("running_summary", "")
    if summary:
        parts.append(f"CONVERSATION SUMMARY (older context):\n{summary}")

    recent = history.get("recent_exchanges", [])
    if recent:
        exchanges_text = "\n\n".join(
            f"User: {ex['user']}\nChairman's answer: {ex['chairman']}"
            for ex in recent
        )
        parts.append(f"RECENT CONVERSATION:\n{exchanges_text}")

    if not parts:
        return ""

    return "\n\n".join(parts) + "\n\n---\n\n"


async def stage1_collect_responses(
    user_query: str,
    council_models: List[Dict[str, Any]],
    history: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Stage 1: Collect individual responses from all council models in parallel.

    Args:
        user_query: The user's question
        council_models: List of model config dicts for this conversation's council
        history: Optional conversation history dict (summary + recent exchanges)

    Returns:
        List of dicts with 'model_id', 'display_name', and 'response' keys
    """
    history_prefix = _build_history_prefix(history)
    prompt = f"{history_prefix}{user_query}"
    messages = [{"role": "user", "content": prompt}]

    # Query all council models in parallel
    responses = await query_models_parallel(council_models, messages)

    # Format results — include only models that responded successfully
    results = []
    for model_config in council_models:
        response = responses.get(model_config["id"])
        if response is not None:
            results.append({
                "model_id": model_config["id"],
                "model": model_config["display_name"],  # used by frontend for display
                "response": response.get("content", ""),
            })

    return results


async def stage2_collect_rankings(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    council_models: List[Dict[str, Any]],
    history: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """
    Stage 2: Each model anonymously reviews and ranks all Stage 1 responses.

    Args:
        user_query: The original user query
        stage1_results: Results from Stage 1
        council_models: List of model config dicts for this conversation's council
        history: Optional conversation history dict

    Returns:
        Tuple of (rankings list, label_to_model mapping)
    """
    # Create anonymized labels (Response A, Response B, ...)
    labels = [chr(65 + i) for i in range(len(stage1_results))]

    # label_to_model maps "Response A" -> display_name for de-anonymization in frontend
    label_to_model = {
        f"Response {label}": result["model"]
        for label, result in zip(labels, stage1_results)
    }

    # Build the anonymized responses block
    responses_text = "\n\n".join(
        f"Response {label}:\n{result['response']}"
        for label, result in zip(labels, stage1_results)
    )

    history_prefix = _build_history_prefix(history)

    ranking_prompt = f"""{history_prefix}You are evaluating different responses to the following question:

Question: {user_query}

Here are the responses from different models (anonymized):

{responses_text}

Your task:
1. First, evaluate each response individually. For each response, explain what it does well and what it does poorly.
2. Then, at the very end of your response, provide a final ranking.

IMPORTANT: Your final ranking MUST be formatted EXACTLY as follows:
- Start with the line "FINAL RANKING:" (all caps, with colon)
- Then list the responses from best to worst as a numbered list
- Each line should be: number, period, space, then ONLY the response label (e.g., "1. Response A")
- Do not add any other text or explanations in the ranking section

Example of the correct format for your ENTIRE response:

Response A provides good detail on X but misses Y...
Response B is accurate but lacks depth on Z...
Response C offers the most comprehensive answer...

FINAL RANKING:
1. Response C
2. Response A
3. Response B

Now provide your evaluation and ranking:"""

    messages = [{"role": "user", "content": ranking_prompt}]

    # All council models rank the responses in parallel
    responses = await query_models_parallel(council_models, messages)

    results = []
    for model_config in council_models:
        response = responses.get(model_config["id"])
        if response is not None:
            full_text = response.get("content", "")
            parsed, fallback_used = parse_ranking_from_text(full_text)
            results.append({
                "model_id": model_config["id"],
                "model": model_config["display_name"],
                "ranking": full_text,
                "parsed_ranking": parsed,
                "ranking_fallback": fallback_used,
            })

    return results, label_to_model


async def stage3_synthesize_final(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]],
    chairman_config: Dict[str, Any],
    history: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Stage 3: The Chairman model synthesizes a final response.

    Args:
        user_query: The original user query
        stage1_results: Individual model responses from Stage 1
        stage2_results: Rankings from Stage 2
        chairman_config: Model config dict for the chairman
        history: Optional conversation history dict

    Returns:
        Dict with 'model' (display name) and 'response' keys
    """
    stage1_text = "\n\n".join(
        f"Model: {r['model']}\nResponse: {r['response']}"
        for r in stage1_results
    )

    stage2_text = "\n\n".join(
        f"Model: {r['model']}\nRanking: {r['ranking']}"
        for r in stage2_results
    )

    history_prefix = _build_history_prefix(history)

    chairman_prompt = f"""{history_prefix}You are the Chairman of a C-Suite AI council. Multiple AI models have provided responses to a user's question, and then ranked each other's responses.

Original Question: {user_query}

STAGE 1 - Individual Responses:
{stage1_text}

STAGE 2 - Peer Rankings:
{stage2_text}

Your task as Chairman is to synthesize all of this information into a single, comprehensive, accurate answer to the user's original question. Consider:
- The individual responses and their insights
- The peer rankings and what they reveal about response quality
- Any patterns of agreement or disagreement

Provide a clear, well-reasoned final answer that represents the council's collective wisdom:"""

    messages = [{"role": "user", "content": chairman_prompt}]

    response = await query_model(chairman_config, messages)

    if response is None:
        return {
            "model": chairman_config.get("display_name", "Chairman"),
            "response": "Error: Unable to generate final synthesis.",
        }

    return {
        "model": chairman_config.get("display_name", "Chairman"),
        "response": response.get("content", ""),
    }


def parse_ranking_from_text(ranking_text: str) -> Tuple[List[str], bool]:
    """
    Parse the FINAL RANKING section from a model's response.

    Returns a tuple of:
        - List of response labels in ranked order (e.g., ["Response C", "Response A", ...])
        - bool indicating whether the fallback regex was used (True = fallback)
    """
    import re

    if "FINAL RANKING:" in ranking_text:
        parts = ranking_text.split("FINAL RANKING:")
        if len(parts) >= 2:
            ranking_section = parts[1]
            # Look for numbered list items: "1. Response A"
            numbered = re.findall(r"\d+\.\s*Response [A-Z]", ranking_section)
            if numbered:
                return [re.search(r"Response [A-Z]", m).group() for m in numbered], False
            # Fallback within FINAL RANKING section
            fallback = re.findall(r"Response [A-Z]", ranking_section)
            if fallback:
                print(f"[ranking] Warning: FINAL RANKING section found but numbered format missing. "
                      f"Fallback extracted {len(fallback)} labels. Response snippet: {ranking_section[:200]}")
                return fallback, True

    # No FINAL RANKING section found — grab any "Response X" patterns from full text
    fallback = re.findall(r"Response [A-Z]", ranking_text)
    if fallback:
        print(f"[ranking] Warning: No FINAL RANKING section. Fallback regex extracted {len(fallback)} "
              f"labels from full response. Snippet: {ranking_text[:200]}")
    return fallback, True


def calculate_aggregate_rankings(
    stage2_results: List[Dict[str, Any]],
    label_to_model: Dict[str, str],
) -> List[Dict[str, Any]]:
    """
    Calculate aggregate rankings across all models' votes.

    Returns a list of dicts sorted by average rank (lower = better).
    """
    from collections import defaultdict

    model_positions: Dict[str, List[int]] = defaultdict(list)

    for ranking in stage2_results:
        parsed, _fallback = parse_ranking_from_text(ranking["ranking"])
        for position, label in enumerate(parsed, start=1):
            if label in label_to_model:
                model_name = label_to_model[label]
                model_positions[model_name].append(position)

    aggregate = []
    for model_name, positions in model_positions.items():
        if positions:
            aggregate.append({
                "model": model_name,
                "average_rank": round(sum(positions) / len(positions), 2),
                "rankings_count": len(positions),
            })

    aggregate.sort(key=lambda x: x["average_rank"])
    return aggregate


async def generate_conversation_title(
    user_query: str,
    chairman_config: Dict[str, Any],
) -> str:
    """
    Generate a short title for a conversation based on the first user message.

    Uses the chairman model for title generation (fast, cheap call).
    Falls back to "New Conversation" if the model fails.
    """
    title_prompt = f"""Generate a very short title (3-5 words maximum) that summarizes the following question.
The title should be concise and descriptive. Do not use quotes or punctuation in the title.

Question: {user_query}

Title:"""

    messages = [{"role": "user", "content": title_prompt}]

    response = await query_model(chairman_config, messages, timeout=30.0)

    if response is None:
        return "New Conversation"

    title = response.get("content", "New Conversation").strip().strip("\"'")

    if len(title) > 50:
        title = title[:47] + "..."

    return title


async def run_full_council(
    user_query: str,
    council_config: Dict[str, Any],
    history: Optional[Dict[str, Any]] = None,
) -> Tuple[List, List, Dict, Dict]:
    """
    Run the complete 3-stage council process for a single question.

    Args:
        user_query: The user's question
        council_config: The locked council snapshot for this conversation.
                        Must have 'council_model_ids' and 'chairman_id' keys,
                        plus the full 'available_models' list to look up configs.
        history: Optional dict with 'running_summary' and 'recent_exchanges'

    Returns:
        Tuple of (stage1_results, stage2_results, stage3_result, metadata)
    """
    from .config import get_chairman, get_models_by_ids

    # Resolve council members from their IDs
    council_model_ids = council_config.get("council_model_ids", [])
    council_models = get_models_by_ids(council_config, council_model_ids)

    chairman = get_chairman(council_config)

    if not council_models:
        return [], [], {
            "model": "error",
            "response": "No council models are configured. Please add models in Settings.",
        }, {}

    if chairman is None:
        return [], [], {
            "model": "error",
            "response": "No chairman model is configured. Please set one in Settings.",
        }, {}

    # Stage 1
    stage1_results = await stage1_collect_responses(user_query, council_models, history)

    if not stage1_results:
        return [], [], {
            "model": "error",
            "response": "All council models failed to respond. Please check your API keys and endpoints.",
        }, {}

    # Stage 2
    stage2_results, label_to_model = await stage2_collect_rankings(
        user_query, stage1_results, council_models, history
    )

    aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)

    # Stage 3
    stage3_result = await stage3_synthesize_final(
        user_query, stage1_results, stage2_results, chairman, history
    )

    metadata = {
        "label_to_model": label_to_model,
        "aggregate_rankings": aggregate_rankings,
    }

    return stage1_results, stage2_results, stage3_result, metadata


async def run_background_summarization(
    conversation_id: str,
    conversation: Dict[str, Any],
    summarization_model: Dict[str, Any],
    raw_exchanges_to_keep: int = 3,
):
    """
    Compress conversation history into a running summary.

    Called after Stage 3 completes, non-blocking (fire-and-forget via asyncio.create_task).
    Silently skips on any error — never crashes the main request flow.

    The exchanges older than `raw_exchanges_to_keep` are compressed together with
    the existing running summary into a new, updated summary.

    Args:
        conversation_id: Used to write the result back to storage
        conversation: Full conversation dict at the time of the trigger
        summarization_model: Model config dict for the summarization model
        raw_exchanges_to_keep: How many recent exchanges to leave as raw (not summarized)
    """
    try:
        from .storage import update_running_summary

        # Extract all complete exchanges (user + chairman pairs) from message history
        messages = conversation.get("messages", [])
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

        if not exchanges:
            return

        # Only compress exchanges that are older than the raw window.
        # If all exchanges fit in the raw window, nothing to compress yet.
        exchanges_to_compress = exchanges[:-raw_exchanges_to_keep] if len(exchanges) > raw_exchanges_to_keep else []
        if not exchanges_to_compress:
            return

        current_summary = conversation.get("running_summary", "")

        # Build the message to the summarization model
        exchanges_text = "\n\n".join(
            f"User: {ex['user']}\nChairman: {ex['chairman']}"
            for ex in exchanges_to_compress
        )
        content_parts = []
        if current_summary:
            content_parts.append(f"Current summary:\n{current_summary}")
        content_parts.append(f"Exchanges to incorporate:\n{exchanges_text}")

        messages_payload = [
            {"role": "system", "content": _SUMMARIZATION_PROMPT},
            {"role": "user", "content": "\n\n".join(content_parts)},
        ]

        response = await query_model(summarization_model, messages_payload, timeout=60.0)

        if response and response.get("content"):
            updated_at = len(exchanges)
            update_running_summary(conversation_id, response["content"], updated_at)
            print(f"[summarization] Updated summary for {conversation_id} at exchange {updated_at}")

    except Exception as e:
        # Best-effort — never let summarization failures surface to the user
        print(f"[summarization] Warning: failed for {conversation_id}: {e}")
