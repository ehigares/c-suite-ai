# LLM Council — Complete Build Specification v2
**Status: ALL DECISIONS LOCKED — Fully audited, ready for implementation**
*Last updated: 2026-03-08*

---

## What We're Building

A modified fork of Andrej Karpathy's [LLM Council](https://github.com/karpathy/llm-council) — a chat interface where multiple AI models debate each other across 3 stages before producing a synthesized final answer.

**Key improvements over the original:**
1. Any OpenAI-compatible API as a model source (OpenRouter, RunPod+Ollama, local Ollama, etc.)
2. Full user configuration through a Settings UI — no code editing required
3. Conversation history carried forward with smart summarization compression
4. Per-conversation council selection (locked for the duration of each conversation)
5. "Wake up models" button with live status indicators for RunPod cold starts
6. Favorites Council for quick pre-selection on new conversations

**Intended audience:** Non-technical users who self-host via a public repo + video tutorial.

---

## How the Original App Works (Reference)

- **Stage 1:** All council models answer the question simultaneously (parallel async calls)
- **Stage 2:** All models review each other's answers (labeled anonymously as Response A/B/C), each outputs a `FINAL RANKING:` numbered list
- **Stage 3:** The Chairman model reads all Stage 1 answers + Stage 2 rankings, writes a final synthesized answer
- Total: 9 API calls per question for a 4-model council (4+4+1). Wall-clock time = slowest model, not their sum.
- Backend: Python/FastAPI on port 8001. Frontend: React+Vite on port 5173. SSE streaming. JSON file storage per conversation.
- Original routes all calls through OpenRouter with one global API key.

**Core technical insight:** Ollama uses an identical API format to OpenRouter. Only the URL and API key differ. The app treats any OpenAI-compatible endpoint interchangeably.

---

## All Decisions

| Topic | Decision |
|---|---|
| Intended users | Wider non-technical audience |
| App hosting | Free public repo — users self-host |
| Technical bar | Accept some technical literacy required; good docs + video bridges gap |
| Model sources | Any OpenAI-compatible API: OpenRouter, RunPod+Ollama, local Ollama, etc. |
| Configuration | Settings UI — no code editing ever required |
| Chairman model | User's choice, set in Settings |
| Council minimum | 2 members (warning shown, not blocked) |
| Council maximum | No hard limit; warning shown above 6 |
| First-run experience | Empty council + Settings panel auto-opens in wizard mode |
| Settings location | Gear icon in sidebar |
| Wizard relaunch | Persistent "Setup Wizard" button in sidebar for convenience |
| Open-weight model hosting | RunPod (serverless, scale-to-zero, ~$0.89/hr RTX 4090) |
| Conversation history | YES — full history carried forward with summarization compression |
| Summarization trigger | Every 5 exchanges, older exchanges compressed into running summary |
| Summarization timing | After Stage 3 completes, background, non-blocking |
| One exchange definition | User question + Chairman answer only (Stage 1/2 debate is internal scaffolding) |
| Raw exchanges sent with each question | User-configurable slider in Settings (default: 3, range: 1–10) |
| Summarization model | Dedicated model set by user in Settings — independent of council and chairman roles |
| Summarization model role | Can be used as summarization only, or also as council member and/or chairman — fully independent |
| No summarization model set | Hard block on starting new conversations; easy reassignment in Settings; backend skips silently as safety net |
| Summarization prompt | Hardcoded, not user-editable (see below) |
| Per-conversation council | YES — selected at start of each new conversation, locked for duration |
| Favorites Council | User-defined default council stored in config, pre-selected in picker for each new conversation |
| Old conversation council | Reloaded fully — old conversations use their original locked council config |
| Model edits in Settings | Only affect future conversations; tooltip explains this to users |
| Missing model on reload | Warning shown, conversation continues with available models only |
| Orphaned chairman/summarization IDs | Detected on config load, field cleared, yellow warning banner shown |
| Wake-up button — when shown | Always shown at start of each conversation and when revisiting |
| Wake-up button — no RunPod | Auto-shows solid green "Models Awake" with tooltip: "No cold-start endpoints in this council" |
| Wake-up button — with RunPod | Red = cold, flashing yellow = warming, solid green = ready |
| Wake-up button — mixed council | Green with tooltip clarifying only RunPod endpoints were checked |
| "Awake" confirmation method | GET {base_url}/models — 200 response = awake; also checks if configured model is loaded |
| RunPod URL detection | String match: `proxy.runpod.net` = RunPod, `openrouter.ai` = OpenRouter, `localhost`/`127.0.0.1` = Local, else = Custom |
| Empty API key handling | Omit Authorization header entirely when api_key is empty string |
| Settings vs. council picker | Settings = model pool management; council picker lives inside new conversation flow |
| Empty pool in council picker | Replace picker with friendly prompt + "Launch Setup Wizard" button |
| Repo | Fork Karpathy's repo, keep name "LLM Council" |
| data/ directory | `.gitkeep` in repo + `mkdir -p` safety net in `config.py` |
| Phase 1 testability | `council_config.example.json` created in Phase 1 (moved from Phase 5) |

---

## Conversation History & Summarization System

### The Problem
Sending full conversation history to 4+ models on every question causes costs and latency to grow linearly with conversation length. Long conversations also risk hitting models' context window limits.

### The Solution: Sliding Window + Periodic Summarization

Every conversation has two components sent to models on each question:

1. **Running Summary** — A compressed summary of all exchanges older than the raw window. Updated every 5 exchanges by the dedicated summarization model. Starts empty.
2. **Raw Recent Exchanges** — The last N exchanges in full detail. N is user-configurable (default: 3, slider range: 1–10).

**One exchange = one user question + one Chairman answer.** Stage 1 and Stage 2 debate content is internal scaffolding and is not included in history.

**What models receive on each question:**
```
[System prompt]
[Running summary — if it exists]
[Last N raw exchanges — user question + Chairman answer pairs]
[Current question]
```

### Summarization Timing
- Triggered after every 5 exchanges
- Runs **after Stage 3 completes**, in the background, non-blocking
- Users never wait for it — their Chairman answer arrives at normal speed
- The updated summary is available for future questions
- If two rapid-fire questions are asked before summarization completes, slightly more raw history is sent — harmless

### Summarization Prompt (Hardcoded)
```
You are maintaining a running summary of a multi-turn conversation for context.
You will be given the current summary (if any) and a set of new exchanges to incorporate.
Write an updated summary of 3–6 sentences covering: the user's overall goal, key decisions
or conclusions reached, important constraints or preferences established, and any open
questions still being worked on. Be factual, concise, and write in third person
(e.g. "The user is trying to..."). Do not editorialize.
```

### No Summarization Model Configured
- **Hard block:** New conversations cannot start without a summarization model assigned
- Clear prompt shown: *"Please set a summarization model in Settings → History before starting a conversation"*
- Easy fix: Settings → History tab → pick any model from pool
- If orphaned (model deleted): orphan detection clears the reference, same block + banner appears
- **Backend safety net:** If somehow triggered without a configured model, skip summarization silently and log warning — never crash

### Storage in Conversation JSON
```json
{
  "conversation_id": "uuid",
  "council_config": { "...locked snapshot of council at creation time..." },
  "running_summary": "The user is designing a database schema for a social app. PostgreSQL was chosen as the database. The council agreed on UUID primary keys for the users table...",
  "summary_last_updated_at_exchange": 10,
  "messages": [
    { "role": "user", "content": "..." },
    { "role": "chairman", "content": "..." }
  ]
}
```

---

## Wake-Up Button Behavior

Shown at the top of every conversation (new and existing).

| Situation | Button State | Tooltip |
|---|---|---|
| No RunPod endpoints in council | Solid green, "Models Awake" | "No cold-start endpoints in this council" |
| RunPod endpoints present, not yet checked | Red, "Wake Up Models" | "Click to wake RunPod endpoints" |
| Warming up (after click) | Flashing yellow, "Waking Up…" | "Contacting endpoints…" |
| All RunPod endpoints responding | Solid green, "Models Awake" | "RunPod endpoints confirmed ready. Cloud models (OpenRouter) are always available." |
| Some endpoints failed | Red with warning | Lists which models didn't respond |

**Health check method:** `GET {base_url}/models` — a 200 response confirms the endpoint is awake. Response body also checked to verify the configured model ID is loaded.

**RunPod detection:** URL string match for `proxy.runpod.net`.

---

## Source Badges

Auto-detected from base URL using string matching. Shown throughout the UI next to model names.

| URL contains | Badge |
|---|---|
| `proxy.runpod.net` | `[RunPod]` |
| `openrouter.ai` | `[OpenRouter]` |
| `localhost` or `127.0.0.1` | `[Local]` |
| Anything else | `[Custom]` |

Same detection logic used in both frontend and backend.

---

## Settings UI Structure

### First-Run (Wizard Mode)
Auto-opens when `council_config.json` doesn't exist or `available_models` is empty. Also accessible any time via the "Setup Wizard" button in the sidebar.

**Step 1 — Welcome:** Brief explanation of what the app does and what they'll need (API keys).
**Step 2 — Add your first model:** Form to add a model (display name, model ID, base URL, API key).
**Step 3 — Add more models:** Same form, with "I'm done" option.
**Step 4 — Choose Chairman:** Dropdown of added models. Brief explanation of Chairman's role.
**Step 5 — Choose Summarization Model:** Dropdown of all models in pool (not limited to council). Explains it's a background utility role — doesn't need to be in the council.
**Step 6 — Done:** Confirmation screen, opens conversation picker.

**Escape behavior:** "Finish Later" button available at any step. Returns to empty state with prompt: *"No models configured yet — click the ⚙️ gear icon or 'Setup Wizard' to get started."* Gear icon reopens wizard if pool is still empty.

### Ongoing Settings (Gear Icon)
Tabbed interface:

**Models tab:**
- List of all models in pool with edit/delete buttons
- Source badge auto-shown next to each model name
- "Add Model" button → form with:
  - Display Name
  - Model ID (with help text: *"For OpenRouter use formats like `openai/gpt-4o`. For Ollama/RunPod use formats like `llama3.3:70b`."* + links to OpenRouter model list and Ollama library)
  - Base URL
  - API Key (masked, password input type)
  - Test Connection button → calls `POST /api/test-connection`
- Info tooltip: *"Changes to models only apply to new conversations. Existing conversations keep their original settings."*

**Defaults tab:**
- Chairman model selector (dropdown of full pool)
- Favorites Council selector (multi-select checklist of full pool — pre-selects these models in every new conversation picker)

**History tab:**
- Raw exchanges slider (1–10, default 3). Label: *"How many recent exchanges to send in full detail"*
- Summarization model selector (dropdown of full pool — any model can serve this role independently)
- Warning banner if no summarization model set: *"No summarization model selected — new conversations are blocked until one is chosen."*

### Warning System
| Condition | Type | Behavior |
|---|---|---|
| 0–1 council members selected in picker | ❌ Error | "Start Conversation" button disabled |
| 2 council members | ⚠️ Warning | "Only 2 models — diversity will be limited." Non-blocking. |
| 7+ council members | ⚠️ Warning | "Large council — expect higher cost and slower responses." Non-blocking. |
| Any `:free` OpenRouter model | ℹ️ Info | "Free models have a 200 requests/day limit." |
| RunPod URL detected | ℹ️ Info | "RunPod models may be cold — use the Wake Up button before starting." |
| Missing model on old conversation load | ⚠️ Warning | "[Model name] is no longer in your pool. Continuing with available models." |
| Orphaned chairman ID | 🟡 Banner | "Your Chairman model has been removed — please reassign one in Settings." Blocks new conversations. |
| Orphaned summarization model ID | 🟡 Banner | "Your Summarization model has been removed — please reassign one in Settings → History." Blocks new conversations. |
| No summarization model set | 🟡 Banner | "No summarization model selected — new conversations are blocked until one is chosen." |

---

## Per-Conversation Council Picker

Lives inside the new conversation flow, not in Settings.

**Flow for starting a new conversation:**
1. User clicks "New Conversation"
2. If pool is empty → show friendly prompt: *"You haven't added any models yet."* + "Launch Setup Wizard" button
3. If pool has models → council picker appears
4. Favorites Council models are pre-checked (if set); user can change selection
5. Source badges shown next to each model name
6. Chairman indicator shows which model is currently set as Chairman
7. Minimum 2 models required — "Start Conversation" button disabled until met
8. User clicks "Start Conversation" → council locked for duration of conversation

**Council display in active conversation:**
- Small model badges shown in the conversation header
- Read-only — cannot be changed mid-conversation

---

## Favorites Council

- Defined in Settings → Defaults tab
- Stored in `council_config.json` as `favorites_council` — array of model IDs
- Pre-checks those models in the council picker when starting any new conversation
- User can still change the selection before starting
- First-time users see nothing pre-selected until Favorites Council is set

---

## Configuration File

**Location:** `data/council_config.json`
**Must be in `.gitignore`** — contains API keys.
**`data/` directory:** Included in repo via `data/.gitkeep`. Also created by `mkdir -p` in `config.py` on startup.

```json
{
  "available_models": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "display_name": "Llama 3.3 70B (RunPod)",
      "model": "llama3.3:70b",
      "base_url": "https://abc123-11434.proxy.runpod.net/v1",
      "api_key": ""
    },
    {
      "id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
      "display_name": "GPT-4o (OpenRouter)",
      "model": "openai/gpt-4o",
      "base_url": "https://openrouter.ai/api/v1",
      "api_key": "sk-or-..."
    }
  ],
  "chairman_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
  "summarization_model_id": "550e8400-e29b-41d4-a716-446655440000",
  "favorites_council": ["550e8400-e29b-41d4-a716-446655440000", "6ba7b810-9dad-11d1-80b4-00c04fd430c8"],
  "history_raw_exchanges": 3
}
```

---

## Security Notes

- API keys stored plaintext in `council_config.json` — acceptable for local/self-hosted use
- `council_config.json` must be in `.gitignore` and never committed
- Settings UI masks API key fields (password input type)
- Keys never logged or stored in conversation JSON files
- README must prominently warn users never to share their `data/` directory

---

## Files to Create / Modify

### New Files
| File | Purpose |
|---|---|
| `frontend/src/components/Settings.jsx` | Model pool management + wizard mode |
| `frontend/src/components/CouncilPicker.jsx` | Per-conversation council selection |
| `frontend/src/components/WakeUpButton.jsx` | Red/yellow/green endpoint status |
| `data/.gitkeep` | Keep data/ directory in repo |
| `data/council_config.example.json` | Pre-filled sample config for testing (created in Phase 1) |
| `RUNPOD_SETUP.md` | Step-by-step RunPod setup guide |

### Modified Backend Files
| File | Changes |
|---|---|
| `backend/config.py` | `mkdir -p data/` on startup; load/save `council_config.json`; orphan detection for chairman and summarization IDs on load |
| `backend/openrouter.py` → `backend/client.py` | Read per-model `base_url` + `api_key` from config dict; omit Authorization header when `api_key` is empty |
| `backend/council.py` | Accept `council_config` dict; pass conversation history (summary + raw window) through all 3 stages; one exchange = user question + Chairman answer only |
| `backend/main.py` | Add new endpoints (see below); load council config per request; pass history to council; trigger background summarization after Stage 3 |

### Modified Frontend Files
| File | Changes |
|---|---|
| `frontend/src/App.jsx` | Add Settings panel, council picker in new conversation flow, wake-up button, wizard relaunch button in sidebar |
| `frontend/src/components/Sidebar.jsx` | Add gear icon, "Setup Wizard" persistent button |

### Unchanged Files
- `backend/storage.py` (schema additions only — running_summary field)
- `backend/__init__.py`
- All existing chat/streaming/tabs components
- `start.sh`

---

## New API Endpoints

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/config` | Return full `council_config.json` (API keys masked in response) |
| POST | `/api/config` | Save updated config |
| GET | `/api/endpoint-status` | Check status of all RunPod endpoints in a given council |
| POST | `/api/wakeup` | Trigger warm-up ping on all RunPod endpoints in a given council |
| POST | `/api/test-connection` | Test a single model config (base URL, API key, model ID); reuses same health check logic as wakeup (`GET {base_url}/models`) |

---

## Build Phases

### Phase 1 — Backend Foundation
- Create `data/.gitkeep` and `data/council_config.example.json` (enables testing from day one)
- Rename `openrouter.py` → `client.py`; update to use per-model config; omit auth header when api_key empty
- Redesign `config.py`: `mkdir -p data/`, load/save `council_config.json`, orphan detection on load
- Update `council.py`: accept history (summary + raw window); one exchange = question + Chairman answer
- Add new API endpoints to `main.py`; trigger background summarization after Stage 3
- Update `storage.py` schema: add `running_summary` and `summary_last_updated_at_exchange` fields
- **Phase 1 smoke tests:** Confirm SSE streaming still works with history injected; confirm history received by models (ask "what did I just ask you?"); confirm empty api_key omits Authorization header

### Phase 2 — Settings UI
- Build `Settings.jsx`: wizard mode + ongoing tabbed management
- Wire to `/api/config` endpoints
- Source badge detection from URL pattern
- Test Connection button per model (calls `/api/test-connection`)
- Warning system implementation
- Favorites Council multi-select in Defaults tab
- "Setup Wizard" persistent sidebar button
- "Finish Later" escape + empty state fallback

### Phase 3 — Council Picker + Wake-Up Button
- Build `CouncilPicker.jsx`: Favorites pre-selection, source badges, chairman indicator, empty pool fallback
- Build `WakeUpButton.jsx`: red/yellow/green states, tooltips, auto-green for non-RunPod councils
- Wire wake-up to `/api/wakeup` and `/api/endpoint-status`
- Model-loaded verification from `/models` response

### Phase 4 — History & Summarization (wiring)
- Verify background summarization trigger fires correctly after Stage 3
- Verify summary stored in conversation JSON
- Verify summary + raw window passed to council on each question
- Test history slider in Settings affects what's sent
- End-to-end test: long conversation (10+ exchanges) to confirm summarization compresses correctly

### Phase 5 — Polish
- Source badges throughout UI
- Full README rewrite with setup instructions and security warnings
- `RUNPOD_SETUP.md`
- Final `.gitignore` update
- Review all warning messages and tooltips for clarity

---

## Dev Journal

| Date | Entry |
|---|---|
| 2026-03-08 | Extended planning session completed. All decisions locked. v1 spec written. |
| 2026-03-08 | Full 21-issue audit completed. All issues resolved and incorporated. v2 spec written. Ready to begin Phase 1. |

---

## Audit Issue Resolution Summary

| # | Issue | Resolution |
|---|---|---|
| 1 | Orphaned chairman/summarization IDs | Detect on config load, clear field, show yellow warning banner, block new conversations |
| 2 | Model edits affect in-progress conversations | Locked snapshots by design; tooltip explains this in Settings |
| 3 | data/ directory missing on first run | .gitkeep in repo + mkdir -p in config.py |
| 4 | Empty API key sends broken Authorization header | Omit header entirely when api_key is empty string |
| 5 | Model ID format confusion | Help text + links in Settings UI under Model ID field |
| 6 | SSE streaming + history injection | Required smoke test at end of Phase 1 |
| 7 | Summarization timing | After Stage 3, background, non-blocking |
| 8 | One exchange definition | User question + Chairman answer only |
| 9 | No summarization model at trigger time | Hard block on new conversations; easy reassignment; backend safety net |
| 10 | Summarization model doubles as council member | No conflict; noted |
| 11 | Summarization prompt not written | Hardcoded prompt specified; not user-editable |
| 12 | RunPod URL detection | String match: proxy.runpod.net / openrouter.ai / localhost / custom |
| 13 | "Awake" confirmation method | GET {base_url}/models; 200 = awake; also checks model is loaded |
| 14 | Wake-up button implies all models ready | Green button + clarifying hover tooltip |
| 15 | Test Connection endpoint missing | Added POST /api/test-connection; reuses health check logic |
| 16 | Summarization model role independence | Fully independent role; can be pool-only, council+summarization, chairman+summarization, or all three |
| 17 | Wizard escape behavior | Finish Later button + empty state prompt + Setup Wizard persistent sidebar button |
| 18 | No default council pre-selection | Favorites Council feature: user-defined default, pre-selected in picker, changeable per conversation |
| 19 | Empty pool in council picker | Replace picker with friendly prompt + Launch Setup Wizard button |
| 20 | Phase ordering dependency | Order confirmed sound; no changes needed |
| 21 | Phase 1 untestable without config | council_config.example.json moved to Phase 1 |

---

## RunPod Setup Summary (for RUNPOD_SETUP.md)

1. Create account at runpod.io
2. Create Network Volume (50–100GB) — persists model weights between cold starts
3. Create Serverless Endpoint using official `ollama/ollama` Docker image
4. Attach the network volume, set `OLLAMA_MODELS` env var to volume mount path
5. Select GPU: RTX 4090 (24GB VRAM) for models up to ~30B; A100 (40GB) for 70B models
6. Pull desired models via RunPod terminal: `ollama pull llama3.3:70b`
7. Note endpoint URL format: `https://[endpoint-id]-11434.proxy.runpod.net`
8. Enter URL in Settings UI — no API key required for Ollama endpoints
9. Use Wake Up button before starting conversations to avoid cold start delays
---

## Sprint 7 — Security & Hardening
*Added 2026-03-08 following third-party code review*

### Motivation
This is a public GitHub repo installed by anyone with their own API keys.
The app must be secure-by-default so every installer is protected.

### Deliverables

#### 1. Password Authentication
- Password set during first-run wizard (new wizard step)
- Hashed with bcrypt, stored in council_config.json
- Backend issues a signed JWT session token on successful login (24hr inactivity timeout)
- All API endpoints require valid token except: GET /, POST /api/login, GET /api/health
- Frontend shows LoginScreen.jsx if no valid token
- Token stored in browser sessionStorage (clears on tab close)
- Failed logins: rate limited to 5 attempts then 15-minute lockout
- New file: frontend/src/components/LoginScreen.jsx

#### 2. API Key Encryption At Rest
- api_key fields in council_config.json encrypted with Fernet (Python cryptography library)
- Encryption key derived from user password via PBKDF2
- Salt stored in data/.salt (never committed to git, added to .gitignore)
- Keys decrypted in memory only when needed for API calls
- Random signing secret stored in data/.secret (also in .gitignore)
- Password change flow re-encrypts all stored keys with new derived key
- If data/.salt is lost, stored keys are unrecoverable — documented clearly

#### 3. Rate Limiting
- Library: slowapi
- POST /api/conversations/stream: 10 requests/minute/IP
- POST /api/conversations: 20 requests/minute/IP
- POST /api/login: 5 requests/minute/IP
- HTTP 429 returned with clear error message
- Frontend shows friendly "Too many requests" message

#### 4. Input Sanitization
- base_url: must be valid http:// or https:// URL
- api_key: strip whitespace, max 200 chars
- display_name: strip HTML, max 50 chars
- model: strip whitespace, max 100 chars
- Applied to POST /api/config and POST /api/test-connection
- Invalid fields return HTTP 422

#### 5. Request Size Limits
- Maximum message size: 32,000 characters
- HTTP 413 returned if exceeded
- Friendly error shown in frontend

#### 6. Security README Section
- What password protects and doesn't protect
- Warning about never exposing port 8001 to the internet
- How to change password
- Explanation of data/.salt and data/.secret — never delete them

### New Dependencies (add to pyproject.toml)
- cryptography (Fernet + PBKDF2)
- bcrypt (password hashing)
- slowapi (rate limiting)
- PyJWT (session tokens)

### New Files
- frontend/src/components/LoginScreen.jsx
- data/.salt (generated on first run, gitignored)
- data/.secret (generated on first run, gitignored)

### Modified Files
- backend/main.py (auth middleware, rate limiting, size limits)
- backend/config.py (encryption/decryption of api_key fields)
- frontend/src/App.jsx (login screen gate)
- frontend/src/components/Settings.jsx (password change flow)
- .gitignore (add data/.salt, data/.secret)
- README.md (security section)
- pyproject.toml (new dependencies)

---

## Sprint 8 — Bug Fixes & Reliability
*Added 2026-03-08 following third-party code review*

### Motivation
Five correctness and reliability issues identified in code review,
plus test suite reorganization.

### Deliverables

#### 1. Fix CORS / Bind Address Mismatch
- Add ALLOWED_ORIGINS environment variable (default: localhost only)
- CORS and uvicorn bind address both derived from this variable
- README documents how to configure for LAN access
- Secure default: localhost-only

#### 2. Fix start.sh Race Condition
- Replace sleep 2 with poll loop hitting GET /api/health every 0.5s
- Times out after 30 seconds with clear error message
- Works on macOS, Linux, and Git Bash on Windows
- GET /api/health returns proper JSON response

#### 3. Schema Validation for POST /api/config
- Full Pydantic model validates config structure before writing to disk
- Validates: model list structure, chairman/summarization IDs exist
  in pool, favorites IDs exist in pool, history_raw_exchanges 1-10
- HTTP 422 with specific field errors on failure
- Frontend displays validation errors clearly

#### 4. Ranking Parse Failure Logging
- Warning log when fallback regex kicks in (includes truncated model response)
- Subtle warning icon in UI on ranking result when fallback was used
- Not a blocking error — informational only

#### 5. Test Suite Reorganization & Expansion
- Move test_pipeline.py → tests/test_pipeline.py
- New: tests/test_config.py (load, orphan detection, save/reload, validation)
- New: tests/test_ranking.py (well-formed, malformed, empty input)
- New: run_tests.sh / run_tests.ps1 test runner scripts
- README documents how to run tests

### Release
- Tag v1.1.0 after all fixes verified
- README updated with v1.0.0 → v1.1.0 changelog
---

## Sprint 9 — Security Polish & Cost Visibility
*Added 2026-03-08 following second third-party code review (v1.1.0)*

### Motivation
Three remaining gaps identified in v1.1.0 review:
- Minimum password length of 4 chars is too low
- Login lockout resets on server restart (memory-only)
- No cost visibility — users don't know API call or token costs upfront

### Deliverables

#### 1. Minimum Password Length — 8 Characters
- Backend: reject passwords under 8 chars with HTTP 422
- Frontend: inline error "Password must be at least 8 characters"
- Existing short-password users: prompted to update on next login
- Password change flow also enforces 8-char minimum
- Tests: 7-char (fail), 8-char (pass), 9-char (pass)

#### 2. Persistent Login Lockout
- Lockout state written to data/.lockout (JSON, gitignored)
- Structure: { "locked_until", "failed_attempts", "last_attempt" }
- Atomic writes (temp file + rename) to prevent corruption
- Loaded on server start, cleared on success or expiry
- data/.lockout added to .gitignore
- Tests: persists across restart, clears on success, clears on expiry

#### 3. Cost Visibility
- New file: frontend/src/utils/costEstimate.js
  - calculateApiCalls(councilSize) → (N × 2) + 1
  - estimateInputTokens(messageText, historyLength) → approximate int
  - formatCostHint(apiCalls, tokenEstimate) → display string
- CouncilPicker.jsx: live API call count below model selection
  (updates as models are selected/deselected)
- ChatInterface.jsx: subtle cost hint in conversation header
  (debounced 300ms token estimate as user types)
- Never show dollar amounts
- Display is subtle: gray text, small font, clearly labeled as estimate

### New Files
- frontend/src/utils/costEstimate.js
- data/.lockout (runtime only, gitignored)

### Modified Files
- backend/main.py (password length validation, lockout persistence)
- frontend/src/components/LoginScreen.jsx (8-char enforcement)
- frontend/src/components/Settings.jsx (8-char on password change)
- frontend/src/components/CouncilPicker.jsx (API call count display)
- frontend/src/components/ChatInterface.jsx (cost hint in header)
- .gitignore (add data/.lockout)
- README.md (updated security section, new minimum documented)
- BUILD_SPEC.md (this entry)

### Release
- Tag v1.2.0 after all changes verified
- Commit: "Sprint 9: security polish + cost visibility"
- Push tag to github.com/ehigares/llm-council