# CLAUDE.md — LLM Council Project Standing Orders

This file contains instructions that Claude Code must follow throughout the entire project.
Read this file completely before doing anything else in any session.

---

## Who This Project Is For

This app is being built for **non-technical users** who will self-host it. Every decision about
naming, UI copy, error messages, and code structure should be made with that audience in mind.
If something would confuse a non-technical user, simplify it.

---

## The Build Specification

The complete project plan lives in `BUILD_SPEC.md` in this folder. It contains every decision
that has been made about this project. **Before writing any code, read BUILD_SPEC.md.**

If you are ever unsure whether something is in scope, check BUILD_SPEC.md first. Do not invent
features or make architectural decisions that aren't documented there without explicitly flagging
it to the user and asking for approval.

---

## Self-Check Rules (Follow These Every Time)

Before considering any task complete, you must run through this checklist:

### 1 — Does it match the spec?
Re-read the relevant section of BUILD_SPEC.md and confirm your implementation matches what
was decided. If you deviated from the spec for a good reason, flag it explicitly:
> "I deviated from the spec here because [reason]. Is that okay?"

### 2 — Did you handle the edge cases?
Every feature in this project has documented edge cases in BUILD_SPEC.md. Check that your
implementation handles them. Key ones to never forget:
- Empty API key → omit Authorization header entirely (never send `Bearer `)
- Orphaned chairman/summarization model IDs → detect on load, clear, show warning banner
- Empty model pool → show friendly prompt, never show empty picker
- No summarization model set → hard block on new conversations
- Missing model in old conversation → warning, continue with available models
- `data/` directory → always `mkdir -p` before writing, `.gitkeep` keeps it in repo

### 3 — Did you test it?
After implementing anything, verify it actually works. Use the `webapp-testing` skill to
open the app in a browser and confirm the behavior visually where possible. For backend
changes, confirm via curl or the browser network tab.

### 4 — Did you update the dev journal?
After completing each sprint task, add a brief entry to `DEV_JOURNAL.md` documenting:
- What you built
- Any decisions you made that weren't in the spec
- Any problems you ran into and how you solved them
- What the next task is

### 5 — Is the code clean and documented?
- Add comments to any logic that isn't immediately obvious
- Use clear variable and function names — no cryptic abbreviations
- Keep functions small and single-purpose
- Never leave TODO comments without flagging them to the user

---

## Architecture Rules (Never Violate These)

- **client.py handles ALL API calls** — no model calls anywhere else
- **Config always loads from `data/council_config.json`** — never hardcode model details
- **One exchange = user question + Chairman answer only** — never include Stage 1/2 in history
- **Summarization runs after Stage 3, non-blocking** — never make the user wait for it
- **API keys never appear in logs, conversation files, or frontend responses**
- **RunPod detection = string match for `proxy.runpod.net`** — same logic front and back
- **Empty `api_key` = omit Authorization header** — never send a blank Bearer token

---

## Sprint Structure

This project is divided into sprints. Work on **one sprint at a time**. Do not start the next
sprint until the current one is complete and verified.

At the start of each sprint:
1. Read this file
2. Read BUILD_SPEC.md sections relevant to the sprint
3. Read DEV_JOURNAL.md to understand what's been done so far
4. Confirm the plan with the user before writing code

At the end of each sprint:
1. Run the sprint's verification checklist
2. Update DEV_JOURNAL.md
3. Tell the user clearly: "Sprint X is complete. Here's what was built and verified. Ready for Sprint X+1 when you are."

---

## Current Sprint Reference

See DEV_JOURNAL.md for the current sprint status.

The full sprint list is:

| Sprint | Focus | Key Deliverables |
|---|---|---|
| 1 | Foundation & Config | client.py, config.py, example config, data/ setup |
| 2 | Backend API & History | New endpoints, council.py history support, storage schema |
| 3 | Settings UI | Wizard, model pool management, tabs, warnings |
| 4 | Council Picker & Wake-Up | CouncilPicker.jsx, WakeUpButton.jsx, Favorites Council |
| 5 | Summarization Wiring | Background summarization trigger, storage, end-to-end test |
| 6 | Polish & Docs | README, RUNPOD_SETUP.md, .gitignore, example config, badges |

---

## Communication Style

- Always explain what you're about to do before doing it
- If something is complex, break it into steps and confirm before proceeding
- Never make large sweeping changes without warning
- If you hit an error you can't resolve in 2 attempts, stop and explain the situation clearly
- Prefer simple, readable solutions over clever ones

---

## Files You Must Never Touch

- Any existing conversation JSON files in `data/conversations/`
- The original `start.sh` unless explicitly asked
- `.env` files

## Files You Must Never Commit

- `data/council_config.json` (contains API keys)
- Any `.env` files
- These must be in `.gitignore` — verify this in Sprint 1

---

---

# Original Codebase Technical Notes
*The following notes came with the original repository and describe important quirks
of the existing codebase. These are preserved so Claude Code is aware of them.*

---

## Backend Structure (`backend/`)

- `council.py`: Core orchestration — stage1, stage2, stage3, parse_ranking_from_text,
  calculate_aggregate_rankings
- `storage.py`: JSON-based conversation storage in `data/conversations/`
- `config.py`: Model configuration (being redesigned in Sprint 1)
- `openrouter.py`: Async HTTP client (being renamed to `client.py` in Sprint 1)
- `main.py`: FastAPI app, SSE streaming endpoints on port 8001

## Frontend Structure (`frontend/`)

- React + Vite, runs on port 5173
- All ReactMarkdown components must be wrapped in `<div className="markdown-content">`
  for proper spacing — this class is defined globally in `index.css`

## Known Quirks

- **Always run backend as `python -m backend.main` from project root** — NOT from
  inside the backend directory. Module import errors will occur otherwise.
- **CORS**: Frontend must match allowed origins in `main.py` CORS middleware
- **Ranking Parse Failures**: If models don't follow format, fallback regex extracts
  any "Response X" patterns in order
- **Metadata is ephemeral**: label_to_model and aggregate_rankings are not persisted
  to storage — only available in live API responses
- **API Connectivity Testing**: Use `test_openrouter.py` to verify API connectivity
  and test model identifiers before adding to council

## Stage 2 Anonymization

Models receive labels "Response A", "Response B", etc. — never model names.
Backend creates mapping: `{"Response A": "openai/gpt-5.1", ...}`
Frontend displays model names in bold after de-anonymization.
---

## Security Architecture (added Sprint 7)

This app handles user API keys and must be treated as a security-sensitive
codebase. Read this section before touching any auth, config, or API code.

### Authentication Flow
- All API endpoints require a valid JWT session token in the Authorization
  header EXCEPT: GET / (frontend), POST /api/login, GET /api/health
- Tokens are issued by POST /api/login, signed with a secret stored in
  data/.secret, and expire after 24 hours of inactivity
- Failed logins are rate-limited: 5 attempts then 15-minute lockout
- The frontend stores the token in sessionStorage (clears on tab close)
- LoginScreen.jsx is shown when no valid token exists

### API Key Encryption
- API keys in council_config.json are encrypted with Fernet
- Encryption key is derived from the user's password via PBKDF2
- Salt is stored in data/.salt — NEVER commit this file, NEVER delete it
- Keys are decrypted in memory only, never written to disk in plaintext
- If data/.salt is deleted, all stored API keys are permanently unrecoverable
- The _strip_council_keys() and key masking functions must remain in place

### Sensitive Files (all gitignored)
- data/council_config.json — contains encrypted API keys
- data/.salt — encryption salt, loss = permanent key loss
- data/.secret — JWT signing secret
- data/conversations/ — user conversation data

### Rate Limiting
- slowapi is used for rate limiting on all endpoints
- Do not remove or bypass rate limit decorators
- Limits: stream=10/min, conversations=20/min, login=5/min

### Input Validation Rules
- base_url: must be valid http:// or https:// URL
- api_key: strip whitespace, max 200 chars
- display_name: strip HTML, max 50 chars  
- model: strip whitespace, max 100 chars
- Message size: max 32,000 characters
- Config schema: validated with Pydantic before any disk write

### CORS & Bind Address
- Backend bind address and CORS origins are both controlled by the
  ALLOWED_ORIGINS environment variable
- Default: localhost only (most secure)
- Never widen CORS without also considering the bind address
- Document any changes to network exposure in README

### General Security Rules
- Never log full API keys — mask as sk-...xxxx
- Never return unmasked keys in any API response
- Never skip input validation "just for testing"
- Always validate config schema before writing to disk
- Rate limit decorators must stay on all public endpoints