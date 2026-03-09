/**
 * Cost estimation utilities for C-Suite AI.
 *
 * Provides API call counts and rough token estimates so users know
 * what a question will cost before sending it. Never shows dollar
 * amounts — those vary too much across providers.
 */

/**
 * Calculate the number of API calls per question for a given council size.
 * Formula: Stage 1 (N) + Stage 2 (N) + Stage 3 (1) = 2N + 1
 *
 * @param {number} councilSize - Number of models in the council
 * @returns {number} Total API calls per question
 */
export function calculateApiCalls(councilSize) {
  if (councilSize < 1) return 0;
  return councilSize * 2 + 1;
}

/**
 * Estimate input tokens for a single model call.
 * Uses the standard approximation of ~4 characters per token.
 * Adds a fixed estimate for the system prompt (~200 tokens).
 *
 * @param {string} messageText - The user's message text
 * @param {number} historyTokens - Estimated tokens from conversation history (0 if first message)
 * @returns {number} Estimated input tokens per model
 */
export function estimateInputTokens(messageText, historyTokens = 0) {
  const messageTokens = Math.ceil((messageText || '').length / 4);
  const systemPromptTokens = 200;
  return messageTokens + historyTokens + systemPromptTokens;
}

/**
 * Format a human-readable cost hint string.
 *
 * @param {number} apiCalls - Total API calls per question
 * @param {number} tokenEstimate - Estimated input tokens per model (0 to omit)
 * @returns {string} Formatted display string
 */
export function formatCostHint(apiCalls, tokenEstimate = 0) {
  let hint = `${apiCalls} API calls per question`;
  if (tokenEstimate > 0) {
    hint += ` · ~${tokenEstimate.toLocaleString()} input tokens per model`;
  }
  return hint;
}

/**
 * Strip common provider prefixes from model display names.
 * "Anthropic: Claude 3.5 Sonnet" → "Claude 3.5 Sonnet"
 * "OpenAI: GPT-4o" → "GPT-4o"
 *
 * @param {string} name - The display name to clean
 * @returns {string} Display name without provider prefix
 */
export function stripProviderPrefix(name) {
  if (!name) return '';
  // Match "Provider: Model Name" pattern
  const match = name.match(/^[A-Za-z0-9]+:\s+(.+)$/);
  return match ? match[1] : name;
}
