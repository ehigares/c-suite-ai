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
pip install httpx fastapi uvicorn
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

## First Run: The Setup Wizard

The first time you open the app, the Settings panel opens automatically in wizard mode.
The wizard walks you through adding your models step by step.

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

---

## Keeping Your API Keys Safe

Your API keys are stored in `data/council_config.json` on your computer. This file
is excluded from Git — it will never be accidentally uploaded if you push the code
somewhere. The example file `data/council_config.example.json` shows the structure
but contains no real keys.

The app never sends your API keys back to the browser. If you open the browser's
developer tools and inspect network responses, you will see keys either masked
(`sk-or-abc...`) or blank — never the full key.

**Do not share your `data/council_config.json` file with anyone.**

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
