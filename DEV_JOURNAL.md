# C-Suite AI — Dev Journal

This file is maintained by Claude Code throughout the project. It is updated at the end of
every sprint and whenever a significant decision or problem is encountered.

---

## Project Status

**Current Sprint:** Sprint 9.5 — Rebrand + Critical Bug Fixes
**Overall Status:** 🟢 Sprint 9.5 complete

---

## Sprint Log

### Sprint 1 — Foundation & Config
**Status:** ✅ Complete
**Goal:** Establish the core backend infrastructure that everything else depends on.

**Tasks:**
- [x] Verify `.gitignore` includes `data/council_config.json` and `.env` files
- [x] Create `data/.gitkeep` so the data/ directory exists in the repo
- [x] Create `data/council_config.example.json` with placeholder values for testing
- [x] Rename `backend/openrouter.py` → `backend/client.py`
- [x] Update `client.py` to read per-model `base_url` and `api_key` from config dict
- [x] Update `client.py` to omit Authorization header when `api_key` is empty
- [x] Redesign `backend/config.py` to load/save `data/council_config.json`
- [x] Add `mkdir -p data/` safety net to `config.py` on startup
- [x] Add orphan detection for `chairman_id` and `summarization_model_id` on config load
- [x] Verify imports load cleanly (all modules import without errors)

**Verification Checklist:**
- [x] All imports load cleanly: `python -c "from backend.config import ...; from backend.client import ...; from backend.council import ...; from backend.storage import ..."`
- [x] `load_config()` returns default dict with `_warnings` key when no config file exists
- [x] `create_conversation()` creates file with `running_summary` and `summary_last_updated_at_exchange` fields
- [x] `build_history()` returns None on empty conversation (no crash)
- [x] Empty `api_key` omits Authorization header (verified in client.py source — `if api_key:` guard)
- [x] Orphan detection: chairman and summarization IDs cleared + warnings added when model not found

**Notes:**
- All backend work was completed across two sessions. Session 1 handled renaming and .gitignore;
  Session 2 (this session) confirmed imports load cleanly and ran logic tests.
- `httpx`, `fastapi`, and `uvicorn` must be installed: `pip install httpx fastapi uvicorn`
- SSE smoke test deferred to Sprint 2 when a real config will be available for end-to-end testing.
  The streaming endpoint code is structurally sound — reviewed and matches original behavior.

---

### Sprint 2 — Backend API & History
**Status:** ✅ Complete
**Goal:** Add new API endpoints and wire conversation history through the council stages.

**Tasks:**
- [x] Add `GET /api/config` endpoint (returns config with masked API keys)
- [x] Add `POST /api/config` endpoint (saves updated config)
- [x] Add `GET /api/endpoint-status` endpoint (pings RunPod endpoints)
- [x] Add `POST /api/wakeup` endpoint (triggers warm-up on RunPod endpoints)
- [x] Add `POST /api/test-connection` endpoint (tests a single model config)
- [x] Update `backend/storage.py` schema to include `running_summary` and `summary_last_updated_at_exchange`
- [x] Update `backend/council.py` to accept conversation history (summary + raw window)
- [x] Implement history injection into Stage 1, 2, and 3 message payloads
- [x] Define one exchange = user question + Chairman answer only
- [x] Update `backend/main.py` to load council config per request and pass history to council
- [x] Implement RunPod URL detection (`proxy.runpod.net` string match) in backend
- [x] Implement background summarization trigger (after Stage 3, non-blocking)
- [x] Use `history_raw_exchanges` from global config in both message handlers

**Verification Checklist:**
- [x] All imports load cleanly after Sprint 2 changes
- [x] `count_exchanges()` returns 5 after 5 exchanges — trigger condition fires correctly
- [x] `build_history(raw=3)` on 5-exchange conversation returns exactly 3 recent exchanges
- [x] Compression candidates = exchanges older than raw window (2 of 5 when raw=3)
- [x] `build_history` on short conversation (< raw window) returns all available exchanges
- [ ] SSE end-to-end smoke test (requires real API keys — deferred, see notes)
- [ ] `/api/test-connection` live test against a real endpoint (deferred)

**Notes:**
- All 5 API endpoints were already in place from Sprint 1 overflow work.
- The two net-new items this sprint: background summarization + `history_raw_exchanges` wiring.
- Background summarization fires at exchange 5, 10, 15, etc. (every 5 exchanges).
  It only compresses exchanges older than `raw_exchanges_to_keep` — if a conversation has
  5 exchanges and raw=3, only exchanges 1–2 are compressed; 3–5 stay raw.
- SSE smoke test still deferred — no real API keys available in this environment.
  Full end-to-end test is planned for Sprint 6 (Polish & Docs).
- `_SUMMARIZATION_PROMPT` is hardcoded in `council.py` per spec (not user-editable).

---

### Sprint 3 — Settings UI
**Status:** ✅ Complete
**Goal:** Build the full Settings interface including first-run wizard.

**Tasks:**
- [x] Create `frontend/src/components/Settings.jsx`
- [x] Build wizard mode (6 steps: Welcome, Add model, Add more, Chairman, Summarization model, Done)
- [x] Add "Finish Later" button to wizard with empty state fallback
- [x] Add "Setup Wizard" persistent button in sidebar
- [x] Build ongoing settings with 3 tabs: Models, Defaults, History
- [x] Models tab: list, add, edit, delete models with source badges
- [x] Models tab: Test Connection button per model
- [x] Models tab: help text for Model ID field
- [x] Models tab: info tooltip about changes only affecting future conversations
- [x] Defaults tab: Chairman selector, Favorites Council multi-select
- [x] History tab: raw exchanges slider (1-10, default 3), summarization model selector
- [x] Implement blocking warning banners (orphaned IDs, no summarization model)
- [x] Wire all settings to `GET /api/config` and `POST /api/config`
- [x] Implement source badge detection from URL (same logic as backend)
- [x] Add gear icon to sidebar
- [ ] Implement full per-conversation warning system (2 members, 7+ members, free models, RunPod cold start) — deferred to Sprint 4 where the council picker lives

**Verification Checklist:**
- [x] Build passes clean (204 modules, 0 errors, 0 warnings)
- [ ] Wizard opens automatically on first run (empty pool) — needs live backend to verify
- [ ] Wizard "Finish Later" closes without crashing — needs live backend to verify
- [ ] Gear icon reopens wizard if pool is still empty — needs live backend to verify
- [ ] "Setup Wizard" button always visible in sidebar — visible in UI
- [ ] Adding a model and saving persists to council_config.json — needs live backend to verify
- [ ] Test Connection shows success/failure correctly — needs live backend to verify
- [ ] Source badges appear correctly for RunPod, OpenRouter, Local, Custom URLs
- [ ] All warning messages appear at the right times — needs live backend to verify
- [ ] Orphaned chairman ID shows warning banner on load — needs live backend to verify

**Notes:**
- Settings panel is a right-side slide-in overlay (580px wide, max 90vw).
- Warning banners appear at the top of the ChatInterface (yellow, amber-colored), visible regardless of whether a conversation is open.
- "New Conversation" button in sidebar is greyed out and disabled when blocking warnings are active. The wrapper div carries a `title` tooltip with the reason.
- Per-conversation picker warnings (2 members, 7+, free models, RunPod cold start) are deferred to Sprint 4 where the CouncilPicker component will live.
- `getSourceBadge()` and `SourceBadge` are exported from Settings.jsx so Sprint 4's CouncilPicker can import them without duplication.
- Wizard saves partial progress on "Finish Later" if at least one model was added.
- All settings changes accumulate in local state; "Save Settings" button writes one batch to the API.
- `_warnings` keys are stripped before calling saveConfig (backend also strips them, but stripping on the frontend too is cleaner).

---

### Sprint 4 — Council Picker & Wake-Up Button
**Status:** ✅ Complete
**Goal:** Build the per-conversation council picker and wake-up button.

**Tasks:**
- [x] Create `frontend/src/components/CouncilPicker.jsx`
- [x] Show picker when "New Conversation" is clicked
- [x] Pre-check Favorites Council models in picker
- [x] Show source badges next to each model in picker
- [x] Show Chairman indicator in picker (crown badge)
- [x] Disable "Start Conversation" button until 2+ models selected
- [x] Show friendly prompt + wizard button when pool is empty
- [x] Lock council for duration of conversation, shown as read-only model badges in header
- [x] Create `frontend/src/components/WakeUpButton.jsx`
- [x] Implement red / flashing yellow / solid green states
- [x] Auto-show green when no RunPod endpoints in council (with tooltip)
- [x] Implement hover tooltips for all states
- [x] Wire to `POST /api/wakeup`
- [x] Store and display per-conversation council config (locked snapshot in conversation header)
- [x] Fix 4 api.js bugs (getConfig response shape, saveConfig body shape, testConnection field name, createConversation empty body)
- [x] Fix main.py: add council_config to Conversation model, mask API keys in council_config before returning
- [x] Fix ChatInterface: input form was only shown on empty conversations — now always visible for multi-turn

**Verification Checklist:**
- [x] Build passes clean (208 modules, 0 errors, 0 warnings)
- [ ] Council picker appears when "New Conversation" is clicked — needs live backend
- [ ] Favorites Council pre-selects correctly — needs live backend
- [ ] Cannot start conversation with fewer than 2 models — logic verified in code
- [ ] Council is locked after starting — stored in conversation JSON, read-only badges in header
- [ ] Wake-up button auto-green with correct tooltip when no RunPod in council — logic verified in code
- [ ] Old conversation loads with its original council config — needs live backend

**Notes:**
- `WakeUpButton` reads RunPod status from `councilModels` prop on mount; resets correctly when conversations switch (via `useEffect` on the prop).
- "Model-loaded verification from /models response" is deferred — the backend `check_endpoint_health` already does this check and returns it in the result; the frontend just reads `r.alive`. The per-model model-ID check happens backend-side.
- Council picker shows inline warnings only for the *selected* models, not the full pool. Warnings: 2-member diversity, 7+ cost, `:free` model limit, RunPod cold-start reminder.
- `CouncilPicker.css` intentionally reuses `.btn-primary` / `.btn-secondary` from `Settings.css` (both are global-ish classes from the same design system).
- `SourceBadge` and `getSourceBadge` are exported from `Settings.jsx` and imported by both `CouncilPicker` and `ChatInterface` — single source of truth for URL detection.

---

### Sprint 5 — Summarization Wiring
**Status:** ✅ Complete
**Goal:** Wire the background summarization system end-to-end.

**Tasks:**
- [x] Implement summarization trigger: fires after every 5 exchanges — was already complete from Sprint 2
- [x] Implement async background call — non-blocking via asyncio.create_task — was already complete
- [x] Use hardcoded summarization prompt — was already complete in council.py
- [x] Store updated summary via update_running_summary() — was already complete
- [x] Pass summary + raw window to council on each question — was already complete
- [x] Fallback: no summarization model -> skip silently — was already complete
- [x] Fix Bug: API keys leaked from POST /api/conversations response — added _strip_council_keys() helper, applied to both POST and GET conversation endpoints
- [x] Fix Bug: WakeUpButton reset on every SSE chunk — added useMemo([], [conversation.id]) in ChatInterface to stabilise array reference
- [x] Write test_pipeline.py — 47 logic tests, no API keys needed, all pass

**Verification Checklist:**
- [x] 47/47 unit tests pass: count_exchanges, build_history, _build_history_prefix, trigger condition, exchange selection, no-op paths
- [x] Silent failure verified: run_background_summarization catches connection errors without raising
- [x] WakeUpButton fix verified: useMemo keyed on conversation.id — reference stable across SSE events
- [x] API key leak fix verified: _strip_council_keys() blanks all api_key fields in council_config before returning from both conversation endpoints
- [x] Frontend build still clean: 208 modules, 0 errors, 0 warnings
- [ ] SSE end-to-end smoke test — see manual test steps below (requires real API keys)

**Manual SSE Smoke Test Steps (requires real API keys):**

Prerequisites:
1. Install dependencies: `pip install httpx fastapi uvicorn`
2. Create `data/council_config.json` (copy from `data/council_config.example.json`, fill in real API keys and model IDs)
3. Start backend: `python -m backend.main` from project root
4. Start frontend: `cd frontend && npm run dev`
5. Open http://localhost:5173 in a browser

Test A — First-run wizard:
1. Delete `data/council_config.json` if it exists
2. Refresh the app — Settings panel should open automatically in wizard mode
3. Complete the wizard: add 2+ models, set Chairman and Summarization model
4. Verify `data/council_config.json` is created with correct structure
5. Verify no API keys are visible in browser DevTools Network responses (check GET /api/config and POST /api/conversations responses)

Test B — Full council conversation (SSE streaming):
1. Click "New Conversation" — CouncilPicker should appear
2. Confirm Favorites Council models are pre-selected
3. Click "Start Conversation" — verify council header badges appear
4. Send a question — verify Stage 1, 2, 3 loading indicators appear in sequence
5. Verify final answer appears in the chat
6. Check backend console — no errors, title generation logged
7. Send 4 more questions (5 total) — after the 5th, check backend console for `[summarization] Updated summary for ... at exchange 5`
8. Open `data/conversations/<id>.json` — verify `running_summary` is non-empty

Test C — History injection:
1. After Test B (5+ exchanges), send a question that references earlier context
2. Check backend console — history prefix should appear in the outgoing prompt (add a temporary print statement to `_build_history_prefix` if needed)
3. Model response should demonstrate awareness of earlier conversation content

Test D — Warning banners:
1. Manually edit `council_config.json`: change `chairman_id` to a non-existent UUID
2. Restart backend — `_warnings` should contain `chairman_orphaned`
3. Refresh frontend — yellow warning banner should appear above chat area
4. "New Conversation" button should be greyed out

Test E — WakeUpButton:
1. Add a RunPod endpoint to the config (or use any URL containing `proxy.runpod.net`)
2. Start a new conversation selecting that model — button should start red
3. Click "Wake Up Models" — button should flash yellow, then resolve
4. If endpoint is live: turns green. If not: stays red with error tooltip.

**Notes:**
- Sprint 5 was primarily a verification and bug-fix sprint. All pipeline code was implemented in Sprint 2; the sprint confirmed correctness via systematic testing.
- The one behaviour change users will notice: WakeUpButton no longer flickers back to red when models respond during streaming. This was a real UX regression that has been fixed.
- `test_pipeline.py` lives in the project root and is safe to run any time: `python test_pipeline.py`

---

### Sprint 6 — Polish & Docs
**Status:** ✅ Complete
**Goal:** Final polish, documentation, and repo preparation for public release.

**Tasks:**
- [x] Rewrite README with setup instructions and security warnings (text-based, non-technical tone)
- [x] Write RUNPOD_SETUP.md (step-by-step RunPod guide)
- [x] Finalize `.gitignore` — already complete from Sprint 1; verified
- [x] Verify `council_config.example.json` is complete — already complete from Sprint 1; verified
- [x] Source badges already throughout UI from Sprints 3–4; no additional work needed
- [x] Add CouncilPicker.css comment documenting Settings.css button class dependency
- [ ] Final end-to-end test: full conversation with RunPod + OpenRouter models — requires real API keys
- [ ] Final end-to-end test: first-run experience (fresh config) — requires real API keys
- [ ] Final end-to-end test: load old conversation with missing model — requires real API keys

**Verification Checklist:**
- [x] README is clear enough for a non-technical user to set up the app
- [x] RUNPOD_SETUP.md walks through RunPod setup completely (account → volume → endpoint → model pull → add to app)
- [x] No API keys can accidentally be committed (gitignore verified from Sprint 1)
- [x] Frontend build still clean: 208 modules, 0 errors, 0 warnings
- [ ] All 3 end-to-end tests pass — requires real API keys (see DEV_JOURNAL Sprint 5 for smoke test steps)

**Notes:**
- README was rewritten from scratch replacing Karpathy's original. Non-technical tone throughout,
  text-based UI descriptions (no screenshot dependencies), covers: what it does, model sources,
  prerequisites, installation, first-run wizard, starting a conversation, settings overview,
  security warning, troubleshooting, tech stack, credits.
- RUNPOD_SETUP.md is a complete standalone guide: account creation, network volume sizing,
  serverless endpoint config (ollama/ollama template, GPU selection, OLLAMA_MODELS env var),
  model pull, URL format, adding to Settings, Wake Up button states, cost tips, troubleshooting.
- .gitignore and council_config.example.json were already production-ready from Sprint 1.
- Source badges (RunPod/OpenRouter/Local/Custom) are already present in Settings, CouncilPicker,
  and ChatInterface from Sprints 3–4.
- CouncilPicker.css now has a comment warning that .btn-primary/.btn-secondary come from Settings.css.

---

### Sprint 7 — Security & Hardening
**Status:** ✅ Complete
**Goal:** Secure the app with password authentication, API key encryption at rest, rate limiting, input validation, and request size limits.

**Tasks:**
- [x] Add `cryptography`, `bcrypt`, `slowapi`, `PyJWT` to `pyproject.toml`
- [x] Add `data/.salt`, `data/.secret` to `.gitignore`
- [x] Implement password hashing (bcrypt) and verification in `config.py`
- [x] Implement Fernet encryption/decryption for API keys (PBKDF2 key derivation)
- [x] Generate/manage salt (`data/.salt`) and JWT secret (`data/.secret`)
- [x] Implement `set_initial_password()`, `change_password()`, `login_and_cache_key()`
- [x] Implement JWT session token creation and validation (24hr expiry)
- [x] Add `POST /api/login` endpoint with lockout after 5 failures (15min)
- [x] Add `POST /api/setup-password` for first-run
- [x] Add `POST /api/change-password` with re-encryption flow
- [x] Add `GET /api/health` and `GET /api/auth/status` endpoints
- [x] Add JWT auth middleware — all endpoints require valid token except public ones
- [x] Integrate slowapi rate limiting: stream=10/min, conversations=20/min, login=5/min
- [x] Add input validation for model config fields (URL, key length, display name, model ID)
- [x] Add 32,000 char message size limit (HTTP 413)
- [x] Create `LoginScreen.jsx` with setup mode and login mode
- [x] Wire auth token into all API calls (`api.js` rewrite with `authHeaders()` and `apiFetch()`)
- [x] Gate App.jsx behind login screen when no valid token exists
- [x] Handle 401/429/413 errors in frontend with friendly messages
- [x] Add Security tab to Settings with password change form
- [x] Update README with full Security section
- [x] Update `pyproject.toml` dependencies

**Verification Checklist:**
- [x] All 47 existing pipeline tests still pass
- [x] 9 new security unit tests pass (hashing, key derivation, encrypt/decrypt, JWT, login, save/load, change password)
- [x] Frontend build clean: 210 modules, 0 errors, 0 warnings
- [x] All backend imports clean
- [x] `data/.salt` and `data/.secret` in `.gitignore`
- [ ] Login flow end-to-end — needs live backend
- [ ] Password change + re-encryption end-to-end — needs live backend
- [ ] Rate limiting returns 429 — needs live backend
- [ ] Message size limit returns 413 — needs live backend
- [ ] First-run wizard password setup — needs live backend

**Notes:**
- `cryptography` package needed `--only-binary=:all:` flag on Windows ARM64 (no Rust toolchain available for source build). Version 46.0.3 has a pre-built wheel.
- The Fernet key is cached in memory after login (`_fernet_key` module global in config.py). Server restart clears it — the next login re-derives it.
- PBKDF2 uses 600,000 iterations (current OWASP recommendation) with SHA-256.
- Password hash stored in `council_config.json` as `password_hash` field — never sent to frontend (stripped in `_mask_api_keys()`).
- `save_config()` preserves the password hash from the existing file when callers don't pass it (since the config dict callers work with doesn't include it).
- Login lockout is in-memory (resets on server restart) — acceptable for single-user self-hosted app.
- Frontend stores JWT in `sessionStorage` (clears on tab close, as specified).
- `apiFetch()` wrapper in api.js handles 401 (triggers login screen), 429, 413, and 422 globally.

---

### Sprint 8 — Bug Fixes & Reliability
**Status:** ✅ Complete
**Goal:** Fix known issues, add schema validation, improve test infrastructure, and tag v1.1.0.

**Tasks:**
- [x] Fix CORS/bind address mismatch — single `ALLOWED_ORIGINS` env var controls both CORS middleware and uvicorn bind address
- [x] Fix `start.sh` race condition — replaced `sleep 2` with health-check poll loop (curl or Python urllib fallback, 30s timeout)
- [x] Add Pydantic schema validation for `POST /api/config` — `CouncilConfigSchema` with `validate_references()` for cross-field checks
- [x] Add ranking parse failure logging + UI warning icon — `parse_ranking_from_text` returns `(labels, fallback_used)` tuple; amber ⚠ icon in Stage 2
- [x] Reorganize test suite — moved `test_pipeline.py` into `tests/` package, added `test_config.py` (30 tests) and `test_ranking.py` (24 tests), created `run_tests.sh` and `run_tests.ps1`
- [x] Delete old root-level `test_pipeline.py`
- [x] Update README with test docs, ALLOWED_ORIGINS docs, and v1.1.0 changelog
- [x] Update DEV_JOURNAL with Sprint 8 completion
- [x] Tag v1.1.0

**Verification Checklist:**
- [x] All 3 test suites pass: pipeline (47), config (30), ranking (24) — 101 total tests
- [x] Frontend build clean: 210 modules, 0 errors, 0 warnings
- [x] All backend imports clean
- [x] `start.sh` poll loop works with both curl and Python fallback
- [x] `CouncilConfigSchema` rejects invalid cross-references (chairman, summarization, favorites, history range)
- [x] Ranking fallback warning icon appears in Stage 2 UI

**Notes:**
- `ALLOWED_ORIGINS` env var defaults to `http://localhost:5173,http://localhost:3000`. If any origin hostname is not localhost/127.0.0.1/::1, uvicorn binds to `0.0.0.0` instead of `127.0.0.1`.
- `parse_ranking_from_text` return type changed from `List[str]` to `Tuple[List[str], bool]`. Both callers updated: `stage2_collect_rankings` propagates `ranking_fallback` flag, `calculate_aggregate_rankings` discards it with `_`.
- Test suite uses custom `check()` function (not pytest) to keep dependencies minimal for self-hosting users.
- Old root-level `test_pipeline.py` deleted; all tests now live in `tests/` package.

---

### Sprint 9 — Security Polish & Cost Visibility
**Status:** ✅ Complete
**Goal:** Raise password minimum, persist login lockout, add cost visibility for API calls and tokens.

**Tasks:**
- [x] Raise minimum password length from 4 to 8 characters (backend + frontend)
- [x] Add `password_too_short` flag to login response for existing short-password users
- [x] Show non-blocking banner when password is below new minimum
- [x] Persist login lockout to `data/.lockout` (JSON, atomic writes)
- [x] Clear lockout on successful login and on expiry
- [x] Add `data/.lockout` to `.gitignore`
- [x] Create `frontend/src/utils/costEstimate.js` — API call count + token estimate utilities
- [x] Add cost hint to CouncilPicker (live API call count as models selected)
- [x] Add cost hint to ChatInterface header (API calls + debounced token estimate)
- [x] Update README with 8-char minimum, v1.2.0 changelog
- [x] Add 9 new tests: password length (6), lockout persistence (9) — total 110 tests
- [x] Tag v1.2.0

**Verification Checklist:**
- [x] All 3 test suites pass: pipeline (47), config (39), ranking (24) — 110 total
- [x] Frontend build clean: 211 modules, 0 errors, 0 warnings
- [x] Password minimum enforced in setup, login, and change flows
- [x] Lockout survives restart, clears on success, clears on expiry
- [x] Cost hint updates live in CouncilPicker and ChatInterface
- [x] Token estimate debounced (300ms) in ChatInterface

**Notes:**
- Password minimum change is non-breaking for existing users: `login_and_cache_key()` in config.py doesn't check length (only verifies bcrypt hash), so existing users with short passwords can still log in. The backend returns `password_too_short: true` from `/api/login` when the password validates but is under 8 chars.
- The frontend shows a non-blocking banner ("Your password is shorter than the new 8-character minimum…") via the existing warning system in App.jsx, directing users to Settings → Security. The banner clears when config is saved (assumed password was changed).
- Lockout is now IP-agnostic (single lockout state vs. per-IP tracking). Acceptable for single-user self-hosted app — simplifies the persistence model.
- `os.replace()` is used for atomic writes on both Windows and POSIX.
- Cost estimate uses the standard ~4 chars/token approximation plus a fixed 200-token system prompt estimate.

---

### Sprint 9.5 — Rebrand to C-Suite AI + Critical Bug Fixes
**Status:** ✅ Complete
**Goal:** Rebrand from LLM Council to C-Suite AI, fix critical bugs found in first live test, add 3-screen new conversation flow.

**Tasks:**
- [x] Rebrand: replace all "LLM Council" / "llm-council" with "C-Suite AI" / "c-suite-ai" across entire codebase
- [x] Update package.json, pyproject.toml, uv.lock name fields
- [x] Update browser tab title, login screen, sidebar, welcome text
- [x] Bug 1 fix: API key decryption corruption — save_config now preserves original encrypted keys when frontend sends masked values
- [x] Bug 2 fix: React hooks violation — moved useMemo before early return in ChatInterface
- [x] Bug 3 fix: Session expiry blank page — handleAuthExpired now clears conversation state before redirecting to login
- [x] Bug 4 fix: Empty conversation pre-loaded — startup shows welcome screen; auto-opens wizard if no models configured
- [x] Bug 5 fix: Restore last active conversation — last conversation ID stored in localStorage, restored after re-login
- [x] Bug 6 fix: Test Connection auth verification — check_endpoint_health now makes a minimal chat completion request to verify API key
- [x] New: 3-screen new conversation flow (Council → Chairman → Summarization)
- [x] New: ChairmanPicker.jsx and SummarizationPicker.jsx components
- [x] New: Per-conversation chairman and summarization model selection (locked into snapshot)
- [x] UX: Actionable error messages in streaming endpoint (replace technical 401 errors)
- [x] UX: stripProviderPrefix utility — model display names never show provider prefix
- [x] Update DEV_JOURNAL, CLAUDE.md, BUILD_SPEC.md with rebrand notes

**Verification Checklist:**
- [x] All 110 tests pass (pipeline 47, config 39, ranking 24)
- [x] Frontend build clean: 213 modules, 0 errors, 0 warnings
- [x] No "LLM Council" references remain in code files
- [x] All hooks in ChatInterface declared before conditional returns
- [ ] Full end-to-end verification — requires live backend with API keys

**Notes:**
- Bug 1 root cause: POST /api/config received masked keys from frontend (e.g. "sk-or-ab...") and re-encrypted them, destroying the original encrypted values. Fix: `save_config()` now detects masked keys (ending with "..." or equal to "***") and preserves the original encrypted value from disk.
- Bug 2 root cause: `useMemo` for councilModels was declared after the `if (!conversation) return` early exit, causing React to see a different number of hooks between renders.
- Bug 6 fix: `check_endpoint_health` now returns `auth_ok` field. After the GET /models check, it makes a minimal POST to /chat/completions with max_tokens=1 to verify the API key is accepted (checks for 401/403).
- 3-screen flow: CouncilPicker now shows "Continue" instead of "Start Conversation". The chairman and summarization model IDs are passed through to `createConversation()` and stored in the conversation snapshot.

---

## Decisions Made During Build

*(Claude Code logs any decisions made during implementation that weren't in the original spec)*

| Date | Sprint | Decision | Reason |
|---|---|---|---|
| 2026-03-08 | 1 | SSE smoke test deferred to Sprint 2 | No real API keys available in dev environment; endpoint code reviewed and confirmed correct structurally |
| 2026-03-08 | 1 | `storage.py` schema additions included in Sprint 1 | `running_summary` and `summary_last_updated_at_exchange` are needed by `build_history()` which is called from `main.py`; coupling made it cleaner to implement together |
| 2026-03-08 | 7 | PBKDF2 iterations set to 600,000 | Current OWASP recommendation for SHA-256; balances security with login speed |
| 2026-03-08 | 7 | Minimum password length: 4 characters | Low bar appropriate for single-user self-hosted app; user controls their own security posture |
| 2026-03-08 | 7 | Login lockout is in-memory only | Resets on server restart; acceptable for single-user app, avoids needing a persistent lockout store |
| 2026-03-08 | 8 | Custom test framework instead of pytest | Keeps dependencies minimal for self-hosting non-technical users; no extra install needed |
| 2026-03-08 | 8 | ALLOWED_ORIGINS controls both CORS and bind address | Single env var prevents mismatch where CORS allows an origin but uvicorn isn't listening on the right interface |
| 2026-03-08 | 8 | parse_ranking_from_text returns tuple | Adding fallback flag as second return value is cleaner than a separate function; only 2 callers to update |
| 2026-03-08 | 9 | Password too short = non-blocking banner | Avoids locking out existing users; they can still use the app while being prompted to update |
| 2026-03-08 | 9 | Lockout is IP-agnostic (single state file) | Single-user app; per-IP tracking unnecessary and complicates disk persistence |
| 2026-03-08 | 9 | No dollar-amount cost display | Pricing varies too much across providers; API call count and token estimate are always accurate |
| 2026-03-09 | 9.5 | Masked keys preserved in save_config | Detecting "..." suffix prevents frontend masked keys from corrupting stored encrypted keys |
| 2026-03-09 | 9.5 | Auth check via minimal chat completion | GET /models is public on OpenRouter; a POST with max_tokens=1 reliably detects invalid keys |
| 2026-03-09 | 9.5 | Per-conversation chairman/summarization | Stored in council snapshot alongside council_model_ids; global config used as fallback |

---

## Problems Encountered & Solutions

*(Claude Code logs any significant problems and how they were resolved)*

| Date | Sprint | Problem | Solution |
|---|---|---|---|
| 2026-03-08 | 7 | `cryptography` package fails to build from source on Windows ARM64 (no Rust toolchain) | Use `--only-binary=:all:` flag to install pre-built wheel (v46.0.3 has ARM64 wheel) |
| 2026-03-09 | 9.5 | API keys corrupted after server restart — all models return 401 | `save_config()` was re-encrypting masked keys from frontend. Fix: detect masked keys and preserve original encrypted values from disk |
| 2026-03-09 | 9.5 | ChatInterface blank page when clicking conversations | `useMemo` was after early return — violated React hooks rules. Fix: move all hooks above conditional returns |
| 2026-03-09 | 9.5 | Test Connection showed Connected even with wrong API key | `check_endpoint_health` only called GET /models (public endpoint). Fix: added minimal POST /chat/completions check to verify auth |
