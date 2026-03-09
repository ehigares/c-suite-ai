# LLM Council — Dev Journal

This file is maintained by Claude Code throughout the project. It is updated at the end of
every sprint and whenever a significant decision or problem is encountered.

---

## Project Status

**Current Sprint:** Sprint 6 — Polish & Docs
**Overall Status:** 🟢 Sprint 6 complete — all sprints done, ready for release

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

## Decisions Made During Build

*(Claude Code logs any decisions made during implementation that weren't in the original spec)*

| Date | Sprint | Decision | Reason |
|---|---|---|---|
| 2026-03-08 | 1 | SSE smoke test deferred to Sprint 2 | No real API keys available in dev environment; endpoint code reviewed and confirmed correct structurally |
| 2026-03-08 | 1 | `storage.py` schema additions included in Sprint 1 | `running_summary` and `summary_last_updated_at_exchange` are needed by `build_history()` which is called from `main.py`; coupling made it cleaner to implement together |

---

## Problems Encountered & Solutions

*(Claude Code logs any significant problems and how they were resolved)*

| Date | Sprint | Problem | Solution |
|---|---|---|---|
| — | — | — | — |
