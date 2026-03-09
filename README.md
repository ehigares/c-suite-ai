# LLM Council

Ask a question and watch a panel of AI models debate it — then have a Chairman model
synthesize the best answer from everything they said.

Instead of asking one AI and hoping for the best, LLM Council sends your question to
several models at once, has them critique each other's answers, and produces a final
response that draws on the best thinking from all of them.

---

## What It Does

When you send a question, three things happen in sequence:

**Stage 1 — Individual responses.** Every model in your council answers your question
independently. Their answers are shown side by side so you can see how different models
approach the same problem.

**Stage 2 — Peer review.** Each model reads the other models' answers (anonymously — no
model knows which answer belongs to whom) and ranks them by accuracy and insight. A
breakdown of who ranked what is shown in the interface.

**Stage 3 — Final answer.** Your designated Chairman model reads everything — the original
responses and the peer rankings — and writes a final, synthesized answer that draws on the
best parts of all the responses.

The app remembers your conversation history. After every 5 exchanges, it quietly summarizes
older parts of the conversation in the background so the models always have context without
being overwhelmed by a long history.

---

## Model Sources

You can mix and match models from different sources in the same council:

**OpenRouter** — A service that gives you access to hundreds of hosted models (GPT-4o,
Claude, Gemini, Llama, and more) through a single API key. You pay per use. Good for
getting started quickly. Get a key at [openrouter.ai](https://openrouter.ai).

**RunPod** — A GPU cloud service where you can run your own private model instances.
More private and often cheaper for heavy use, but requires some setup. See
[RUNPOD_SETUP.md](RUNPOD_SETUP.md) for a step-by-step walkthrough.

**Local (Ollama)** — If you have Ollama installed and running on your own computer,
LLM Council can talk to it directly. No API key needed. The base URL is
`http://localhost:11434/v1`.

**Custom** — Any service that speaks the OpenAI API format. If you have another
provider, enter its base URL and API key.

You can use any combination of these in the same council. For example: two local Ollama
models plus one OpenRouter model as the Chairman.

---

## Prerequisites

Before you start, you need the following installed on your computer:

- **Python 3.10 or newer** — [python.org](https://www.python.org/downloads/)
- **Node.js 18 or newer** — [nodejs.org](https://nodejs.org/)
- **Git** — [git-scm.com](https://git-scm.com/)

You also need at least one AI model to talk to. The easiest way to start is with an
OpenRouter account and API key. For running models locally or privately, see
[RUNPOD_SETUP.md](RUNPOD_SETUP.md).

---

## Installation

Open a terminal (Command Prompt or PowerShell on Windows, Terminal on Mac/Linux) and
run these commands one at a time:

```bash
git clone https://github.com/YOUR-USERNAME/llm-council.git
cd llm-council
```

**Install Python dependencies:**
```bash
pip install httpx fastapi uvicorn cryptography bcrypt slowapi PyJWT
```

**Install frontend dependencies:**
```bash
cd frontend
npm install
cd ..
```

---

## Starting the App

You need two terminal windows open at the same time — one for the backend server
and one for the frontend.

**Terminal 1 — Backend:**
```bash
python -m backend.main
```

You should see: `Uvicorn running on http://0.0.0.0:8001`

**Terminal 2 — Frontend:**
```bash
cd frontend
npm run dev
```

You should see: `Local: http://localhost:5173`

Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## First Run: Password & Setup Wizard

The first time you open the app, you'll be asked to set a password. This password:

- Protects your instance from unauthorized access
- Encrypts all your stored API keys on disk

Choose something you'll remember — if you lose it, there's no reset mechanism. Your
API keys would need to be re-entered.

After setting a password, the Settings wizard opens automatically and walks you through
adding your models step by step.

**Step 1 — Add your first model.** Fill in:
- *Display name* — whatever you want to call it (e.g. "GPT-4o")
- *Model ID* — the exact model identifier the API expects (e.g. `openai/gpt-4o`)
- *API Base URL* — where to send requests (e.g. `https://openrouter.ai/api/v1`)
- *API Key* — your key for that service (leave blank for local models)

Click "Test Connection" to confirm it works before moving on.

**Step 2 — Add more models.** The council works best with 2–6 models. You can add
as many as you like and choose which ones to use per conversation.

**Step 3 — Choose a Chairman.** This is the model that writes the final synthesized
answer. Pick your best/most capable model for this role.

**Step 4 — Choose a Summarization model.** This model runs quietly in the background
to compress old conversation history. Any model works here — it doesn't need to be
your best one.

**Done.** Click "Start Using LLM Council" and you're ready to go.

You can reopen Settings any time by clicking the gear icon (⚙) at the bottom of
the left sidebar.

---

## Starting a Conversation

Click **"New Conversation"** in the left sidebar. A picker appears showing all your
models. Check the ones you want in this council (they stay locked for the whole
conversation). Click **"Start Conversation"**.

The top of the chat shows colored badges for each model in your council, plus a
**"Wake Up Models"** button if any of your models are running on RunPod (which can
go to sleep between requests). Click it before sending your first question to make
sure they're ready.

Type your question and press Enter (or click Send). The three stages run one after
another — you'll see progress indicators as each stage completes.

---

## Settings Overview

Open Settings with the gear icon (⚙) in the sidebar.

**Models tab** — Add, edit, or remove models. Each model shows a colored badge
indicating its source (RunPod, OpenRouter, Local, or Custom). Use "Test Connection"
to verify a model is reachable before using it in a council.

**Defaults tab** — Set your default Chairman and choose your Favorites Council
(the models that get pre-selected every time you start a new conversation).

**History tab** — Controls how much conversation history the models can see.
"Raw exchanges to keep" sets how many recent back-and-forth messages are sent
in full. Older messages are compressed into a summary automatically.

**Security tab** — Change your password. When you change it, all stored API keys
are automatically re-encrypted.

---

## Security

### What the password protects

- **Unauthorized access** — all API endpoints require a valid session. Without your
  password, nobody can use your council or see your conversations.
- **API key exposure** — your API keys are encrypted at rest using a key derived from
  your password. The raw keys never touch disk after initial setup.

### What it does NOT protect

- **Physical file access** — someone with direct access to your computer can read the
  encrypted config file. The encryption protects against casual exposure (e.g., if the
  file is accidentally copied or shared), not a determined attacker with full disk access.

### Important files in `data/`

| File | What it is | What happens if deleted |
|---|---|---|
| `council_config.json` | Your encrypted config + API keys | All settings lost; re-run setup |
| `.salt` | Encryption salt for PBKDF2 key derivation | **All stored API keys become permanently unrecoverable** |
| `.secret` | JWT signing secret | All active sessions invalidated (re-login required) |
| `conversations/` | Your conversation history | Conversations lost |

**Never delete `data/.salt`** unless you're intentionally starting from scratch. If it's
lost, you'll need to re-enter all your API keys.

All files in `data/` are excluded from Git and will never be accidentally committed.

### Network security

**Never expose port 8001 to the public internet** without additional protection
(VPN, reverse proxy with TLS, etc.). LLM Council is designed for local or LAN use.
The default configuration only allows connections from localhost.

### Changing your password

Go to Settings (gear icon) → Security tab. Enter your current password and your new
password. All stored API keys are automatically re-encrypted with the new password.

### Rate limiting

The app rate-limits requests to prevent abuse:
- Chat messages: 10 per minute
- Other API calls: 20 per minute
- Login attempts: 5 per minute (locked out for 15 minutes after 5 failures)

---

## Running Tests

The test suite runs without API keys or a running server — it tests pure logic only.

**On Mac/Linux:**
```bash
./run_tests.sh
```

**On Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy Bypass -File run_tests.ps1
```

**Or run individual suites:**
```bash
python -m tests.test_pipeline    # History, summarization, exchange logic (47 tests)
python -m tests.test_config      # Config loading, encryption, schema validation (30 tests)
python -m tests.test_ranking     # Ranking parse logic — well-formed, malformed, edge cases (24 tests)
```

---

## LAN Access

By default, LLM Council only accepts connections from `localhost`. To access it from
other devices on your local network (e.g., a phone or another computer), set the
`ALLOWED_ORIGINS` environment variable before starting the backend:

```bash
ALLOWED_ORIGINS="http://localhost:5173,http://192.168.1.100:5173" python -m backend.main
```

Replace `192.168.1.100` with your computer's LAN IP address. When any origin hostname
is not `localhost`, `127.0.0.1`, or `::1`, the backend automatically binds to `0.0.0.0`
(all network interfaces) instead of localhost only.

**Important:** Never expose the backend to the public internet without additional
protection (VPN, reverse proxy with TLS, firewall rules). LLM Council is designed
for local and trusted-LAN use only.

---

## Troubleshooting

**"No valid council models selected" when starting a conversation**
The models you selected aren't found in the config. This can happen if you edited
the config file by hand. Open Settings → Models and check that your models are
listed correctly.

**"No chairman model configured" error**
Go to Settings → Defaults and assign a Chairman model. Every conversation requires one.

**Warning banner: "Your Chairman model has been removed from the pool"**
You deleted a model that was set as Chairman. Go to Settings → Defaults and choose
a new one. New conversations are blocked until this is fixed.

**Warning banner: "No summarization model selected"**
Go to Settings → History and pick a model. This is required before you can start
a new conversation.

**Models not responding / connection errors**
Use the "Test Connection" button in Settings → Models to check each model individually.
For RunPod models, make sure the endpoint is awake — use the "Wake Up Models" button
at the top of a conversation, or check your RunPod dashboard.

**"Module not found" errors when starting the backend**
Make sure you're running `python -m backend.main` from the project root directory,
not from inside the `backend/` folder.

**Frontend shows a blank page or "Failed to fetch"**
The backend isn't running. Start it with `python -m backend.main` and refresh.

---

## Tech Stack

- **Backend:** Python 3.10+, FastAPI, async httpx
- **Frontend:** React, Vite, react-markdown
- **Storage:** JSON files in `data/conversations/` — no database needed
- **Model API:** OpenAI-compatible (works with OpenRouter, RunPod/Ollama, local Ollama, and more)

---

## Credits

Based on the original [llm-council](https://github.com/karpathy/llm-council) concept by
Andrej Karpathy. This fork adds a full settings UI, multi-source model support, RunPod
integration, conversation history with background summarization, and a first-run wizard.

---

## Changelog

### v1.1.0 — Bug Fixes & Reliability

- **CORS/bind address fix** — New `ALLOWED_ORIGINS` env var controls both CORS and
  server bind address. Prevents mismatch where CORS allows a LAN origin but the server
  only listens on localhost.
- **start.sh race condition fix** — Backend startup now polls `/api/health` instead of
  using a fixed `sleep 2`, so the frontend won't launch before the backend is ready.
- **Config schema validation** — `POST /api/config` now validates with Pydantic before
  saving. Invalid cross-references (orphaned chairman, bad favorites) are rejected with
  clear error messages.
- **Ranking parse warning** — When a model doesn't follow the expected FINAL RANKING
  format, an amber ⚠ icon appears next to its ranking tab in Stage 2.
- **Test suite** — 101 tests across 3 suites (pipeline, config, ranking). No API keys
  needed. Run with `./run_tests.sh` or `run_tests.ps1`.

### v1.0.0 — Initial Release

- Full settings UI with first-run wizard
- Multi-source model support (OpenRouter, RunPod, Local/Ollama, Custom)
- Password authentication with API key encryption at rest
- Conversation history with background summarization
- Rate limiting and input validation
- RunPod wake-up button with endpoint health checking
