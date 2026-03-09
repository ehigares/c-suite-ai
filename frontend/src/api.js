/**
 * API client for the C-Suite AI backend.
 *
 * All authenticated requests include the JWT token from sessionStorage.
 * If a 401 response is received, the onAuthExpired callback is triggered
 * so the app can show the login screen.
 */

const API_BASE = 'http://localhost:8001';

// Callback set by the app when auth expires — triggers login screen
let _onAuthExpired = null;

/**
 * Register a callback to be called when the session token expires.
 * The App component sets this on mount.
 */
export function setOnAuthExpired(callback) {
  _onAuthExpired = callback;
}

/**
 * Get the current auth token from sessionStorage.
 */
function getToken() {
  return sessionStorage.getItem('council_token');
}

/**
 * Save the auth token to sessionStorage.
 */
export function setToken(token) {
  sessionStorage.setItem('council_token', token);
}

/**
 * Clear the auth token from sessionStorage.
 */
export function clearToken() {
  sessionStorage.removeItem('council_token');
}

/**
 * Build headers for authenticated requests.
 */
function authHeaders(extra = {}) {
  const headers = { 'Content-Type': 'application/json', ...extra };
  const token = getToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

/**
 * Shared fetch wrapper that handles 401 (auth expired) and error responses.
 */
async function apiFetch(url, options = {}) {
  const response = await fetch(url, options);

  if (response.status === 401) {
    clearToken();
    if (_onAuthExpired) _onAuthExpired();
    throw new Error('Session expired. Please log in again.');
  }

  if (response.status === 429) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || 'Too many requests. Please wait a moment and try again.');
  }

  if (response.status === 413) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || 'Message too long.');
  }

  if (response.status === 422) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || 'Invalid input.');
  }

  return response;
}

export const api = {
  // ── Auth endpoints (no token needed) ─────────────────────────────────

  /**
   * Check if a password has been set (determines login vs setup screen).
   */
  async getAuthStatus() {
    const response = await fetch(`${API_BASE}/api/auth/status`);
    if (!response.ok) throw new Error('Failed to check auth status');
    return response.json();
  },

  /**
   * Log in with a password. Returns { token }.
   */
  async login(password) {
    const response = await fetch(`${API_BASE}/api/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password }),
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || 'Login failed.');
    }
    return response.json();
  },

  /**
   * Set the initial password during first-run setup. Returns { token }.
   */
  async setupPassword(password) {
    const response = await fetch(`${API_BASE}/api/setup-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password }),
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || 'Setup failed.');
    }
    return response.json();
  },

  /**
   * Change the password. Returns { token, message }.
   */
  async changePassword(oldPassword, newPassword) {
    const response = await apiFetch(`${API_BASE}/api/change-password`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || 'Password change failed.');
    }
    return response.json();
  },

  // ── Authenticated endpoints ──────────────────────────────────────────

  /**
   * List all conversations.
   */
  async listConversations() {
    const response = await apiFetch(`${API_BASE}/api/conversations`, {
      headers: authHeaders(),
    });
    if (!response.ok) throw new Error('Failed to list conversations');
    return response.json();
  },

  /**
   * Create a new conversation with a locked council snapshot.
   * @param {string[]} councilModelIds - UUIDs of models selected for this conversation
   * @param {string} [chairmanId] - Override chairman for this conversation
   * @param {string} [summarizationModelId] - Override summarization model for this conversation
   */
  async createConversation(councilModelIds, chairmanId, summarizationModelId) {
    const body = { council_model_ids: councilModelIds };
    if (chairmanId) body.chairman_id = chairmanId;
    if (summarizationModelId) body.summarization_model_id = summarizationModelId;
    const response = await apiFetch(`${API_BASE}/api/conversations`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || 'Failed to create conversation');
    }
    return response.json();
  },

  /**
   * Get a specific conversation.
   */
  async getConversation(conversationId) {
    const response = await apiFetch(
      `${API_BASE}/api/conversations/${conversationId}`,
      { headers: authHeaders() }
    );
    if (!response.ok) throw new Error('Failed to get conversation');
    return response.json();
  },

  /**
   * Send a message in a conversation.
   */
  async sendMessage(conversationId, content) {
    const response = await apiFetch(
      `${API_BASE}/api/conversations/${conversationId}/message`,
      {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ content }),
      }
    );
    if (!response.ok) throw new Error('Failed to send message');
    return response.json();
  },

  /**
   * Load the full council config. API keys are masked in the response.
   * Backend returns { config: {...}, warnings: [...] } — normalized here to
   * a flat config object with _warnings attached so callers see one thing.
   */
  async getConfig() {
    const response = await apiFetch(`${API_BASE}/api/config`, {
      headers: authHeaders(),
    });
    if (!response.ok) throw new Error('Failed to load config');
    const data = await response.json();
    return { ...data.config, _warnings: data.warnings || [] };
  },

  /**
   * Save the full council config.
   * Backend SaveConfigRequest expects { "config": {...} } as the body.
   * Internal keys (starting with _) are stripped by the backend before writing.
   */
  async saveConfig(config) {
    const response = await apiFetch(`${API_BASE}/api/config`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ config }),
    });
    if (!response.ok) throw new Error('Failed to save config');
    return response.json();
  },

  /**
   * Test connectivity to a single model endpoint.
   * Backend TestConnectionRequest field is named 'model' (not 'model_id').
   * @param {{ model: string, base_url: string, api_key: string }} modelConfig
   */
  async testConnection({ model, base_url, api_key }) {
    const response = await apiFetch(`${API_BASE}/api/test-connection`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ model, base_url, api_key }),
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || 'Connection test failed');
    }
    return response.json();
  },

  /**
   * Trigger a wake-up ping on all RunPod endpoints in the given council.
   * @param {string[]} councilModelIds - UUIDs of models in the current council
   */
  async wakeup(councilModelIds) {
    const response = await apiFetch(`${API_BASE}/api/wakeup`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ council_model_ids: councilModelIds }),
    });
    if (!response.ok) throw new Error('Wake-up request failed');
    return response.json();
  },

  /**
   * Send a message and receive streaming updates.
   * @param {string} conversationId - The conversation ID
   * @param {string} content - The message content
   * @param {function} onEvent - Callback function for each event: (eventType, data) => void
   * @returns {Promise<void>}
   */
  async sendMessageStream(conversationId, content, onEvent) {
    const response = await apiFetch(
      `${API_BASE}/api/conversations/${conversationId}/message/stream`,
      {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ content }),
      }
    );

    if (!response.ok) {
      throw new Error('Failed to send message');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value);
      const lines = chunk.split('\n');

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6);
          try {
            const event = JSON.parse(data);
            onEvent(event.type, event);
          } catch (e) {
            console.error('Failed to parse SSE event:', e);
          }
        }
      }
    }
  },
};
