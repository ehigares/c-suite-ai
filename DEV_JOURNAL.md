# LLM Council — Dev Journal

This file is maintained by Claude Code throughout the project. It is updated at the end of
every sprint and whenever a significant decision or problem is encountered.

---

## Project Status

**Current Sprint:** Sprint 3 — Settings UI
**Overall Status:** 🟢 Sprint 2 complete — ready for Sprint 3

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
**Status:** ⏳ Waiting for Sprint 2
**Goal:** Build the full Settings interface including first-run wizard.

**Tasks:**
- [ ] Create `frontend/src/components/Settings.jsx`
- [ ] Build wizard mode (6 steps: Welcome, Add model, Add more, Chairman, Summarization model, Done)
- [ ] Add "Finish Later" button to wizard with empty state fallback
- [ ] Add "Setup Wizard" persistent button in sidebar
- [ ] Build ongoing settings with 3 tabs: Models, Defaults, History
- [ ] Models tab: list, add, edit, delete models with source badges
- [ ] Models tab: Test Connection button per model
- [ ] Models tab: help text for Model ID field with links
- [ ] Models tab: info tooltip about changes only affecting future conversations
- [ ] Defaults tab: Chairman selector, Favorites Council multi-select
- [ ] History tab: raw exchanges slider (1-10, default 3), summarization model selector
- [ ] Implement all warning banners (orphaned IDs, no summarization model, etc.)
- [ ] Implement full warning system (2 members, 7+ members, free models, RunPod cold start)
- [ ] Wire all settings to `GET /api/config` and `POST /api/config`
- [ ] Implement source badge detection from URL (same logic as backend)
- [ ] Add gear icon to sidebar

**Verification Checklist:**
- [ ] Wizard opens automatically on first run (empty pool)
- [ ] Wizard "Finish Later" closes without crashing
- [ ] Gear icon reopens wizard if pool is still empty
- [ ] "Setup Wizard" button always visible in sidebar
- [ ] Adding a model and saving persists to council_config.json
- [ ] Test Connection shows success/failure correctly
- [ ] Source badges appear correctly for RunPod, OpenRouter, Local, Custom URLs
- [ ] All warning messages appear at the right times
- [ ] Orphaned chairman ID shows warning banner on load

**Notes:**
*(Claude Code adds notes here as work progresses)*

---

### Sprint 4 — Council Picker & Wake-Up Button
**Status:** ⏳ Waiting for Sprint 3
**Goal:** Build the per-conversation council picker and wake-up button.

**Tasks:**
- [ ] Create `frontend/src/components/CouncilPicker.jsx`
- [ ] Show picker when "New Conversation" is clicked
- [ ] Pre-check Favorites Council models in picker
- [ ] Show source badges next to each model in picker
- [ ] Show Chairman indicator in picker
- [ ] Disable "Start Conversation" button until 2+ models selected
- [ ] Show friendly prompt + wizard button when pool is empty
- [ ] Lock council for duration of conversation, show as read-only in header
- [ ] Create `frontend/src/components/WakeUpButton.jsx`
- [ ] Implement red / flashing yellow / solid green states
- [ ] Auto-show green when no RunPod endpoints in council (with tooltip)
- [ ] Implement hover tooltips for all states
- [ ] Wire to `POST /api/wakeup` and `GET /api/endpoint-status`
- [ ] Implement model-loaded verification from `/models` response
- [ ] Show warning if a configured model isn't loaded on the endpoint
- [ ] Store and display per-conversation council config (locked snapshot)

**Verification Checklist:**
- [ ] Council picker appears before message input on new conversation
- [ ] Favorites Council pre-selects correctly
- [ ] Cannot start conversation with fewer than 2 models
- [ ] Council is locked after starting — cannot be changed mid-conversation
- [ ] Wake-up button turns green when RunPod endpoint responds to GET /models
- [ ] Wake-up button auto-green with correct tooltip when no RunPod in council
- [ ] Old conversation loads with its original council config

**Notes:**
*(Claude Code adds notes here as work progresses)*

---

### Sprint 5 — Summarization Wiring
**Status:** ⏳ Waiting for Sprint 4
**Goal:** Wire the background summarization system end-to-end.

**Tasks:**
- [ ] Implement summarization trigger: fires after every 5 exchanges
- [ ] Implement async background call — non-blocking, user never waits
- [ ] Use hardcoded summarization prompt (see BUILD_SPEC.md)
- [ ] Store updated summary in conversation JSON after each summarization
- [ ] Pass summary + raw window (user-configured N exchanges) to council on each question
- [ ] Implement fallback: if no summarization model configured, skip silently and log warning
- [ ] Test slider in Settings correctly changes how many raw exchanges are sent

**Verification Checklist:**
- [ ] After 5 exchanges, summary is generated and stored in conversation JSON
- [ ] Summary appears in model prompts on subsequent questions (verify via logs)
- [ ] User experiences no delay — summarization is truly non-blocking
- [ ] Changing the raw exchanges slider changes what's sent (verify via logs)
- [ ] With no summarization model set, app doesn't crash — skips silently
- [ ] Long conversation (10+ exchanges) maintains coherent context throughout

**Notes:**
*(Claude Code adds notes here as work progresses)*

---

### Sprint 6 — Polish & Docs
**Status:** ⏳ Waiting for Sprint 5
**Goal:** Final polish, documentation, and repo preparation for public release.

**Tasks:**
- [ ] Rewrite README with setup instructions, screenshots, and security warnings
- [ ] Write RUNPOD_SETUP.md (step-by-step RunPod guide)
- [ ] Finalize `.gitignore` (council_config.json, .env, __pycache__, node_modules, etc.)
- [ ] Verify `council_config.example.json` is complete and well-commented
- [ ] Add source badges throughout UI wherever model names appear
- [ ] Review all warning messages and tooltips for clarity
- [ ] Final end-to-end test: full conversation with RunPod + OpenRouter models
- [ ] Final end-to-end test: first-run experience (fresh config)
- [ ] Final end-to-end test: load old conversation with missing model

**Verification Checklist:**
- [ ] README is clear enough for a non-technical user to set up the app
- [ ] RUNPOD_SETUP.md walks through RunPod setup completely
- [ ] No API keys can accidentally be committed (gitignore verified)
- [ ] All 3 end-to-end tests pass
- [ ] App looks polished and professional throughout

**Notes:**
*(Claude Code adds notes here as work progresses)*

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
