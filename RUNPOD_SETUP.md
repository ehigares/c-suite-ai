# RunPod Setup Guide

This guide walks you through running a model on RunPod so you can use it in LLM Council.
RunPod lets you rent a GPU in the cloud and run any Ollama-compatible model on it privately.

You do not need to be a developer to follow these steps.

---

## Why RunPod?

- **Privacy** — Your queries go to your own private GPU instance, not a shared service.
- **Cost** — For models you use heavily, a RunPod instance can be cheaper than paying
  per-token through OpenRouter.
- **Model selection** — You can run almost any open-source model (Llama, Mistral, Qwen,
  DeepSeek, and hundreds more).

The trade-off: RunPod instances can "go to sleep" after a period of inactivity and take
30–90 seconds to wake back up. LLM Council has a **Wake Up Models** button to handle this.

---

## Step 1 — Create a RunPod Account

1. Go to [runpod.io](https://www.runpod.io) and click **Sign Up**.
2. Create an account and verify your email.
3. Add a payment method. RunPod charges by the hour for active GPU usage — there is no
   subscription fee. Costs vary by GPU but are typically $0.20–$1.00/hour.

---

## Step 2 — Create a Network Volume (Storage)

A Network Volume stores your downloaded models so they persist between sessions.
Without one, you'd have to re-download the model every time the pod starts.

1. In the RunPod dashboard, click **Storage** in the left menu.
2. Click **+ New Network Volume**.
3. Settings:
   - **Name:** anything you like (e.g. `ollama-models`)
   - **Size:** at least **50 GB** for a 7B model; **100 GB** for a 70B model
   - **Region:** choose the same region you'll use for your serverless endpoint (next step)
4. Click **Create** and wait for it to be ready.

---

## Step 3 — Create a Serverless Endpoint

A Serverless Endpoint is a GPU instance that spins up on demand and sleeps when idle.
This is the most cost-effective way to run models you don't use constantly.

1. In the RunPod dashboard, click **Serverless** in the left menu.
2. Click **+ New Endpoint**.
3. On the configuration screen:

   **Template:** Search for `ollama` and select **`ollama/ollama`**.

   **GPU:** Choose based on the model size you want to run:
   - Small models (7B, 8B) — RTX 4090 or A4000 (24 GB VRAM)
   - Medium models (13B, 14B) — A5000 or 3090 (24 GB VRAM, run at 4-bit)
   - Large models (70B) — A100 or H100 (80 GB VRAM)

   **Min Workers:** Set to `0` (sleeps when not in use, saves cost).
   **Max Workers:** Set to `1` (only one instance at a time).

   **Network Volume:** Select the volume you created in Step 2.

4. Under **Advanced**, look for **Environment Variables** and add:
   - Key: `OLLAMA_MODELS`
   - Value: `/runpod-volume/ollama`

   This tells Ollama to store downloaded models on your persistent volume.

5. Click **Deploy**. Wait a few minutes for the endpoint to be created.

---

## Step 4 — Find Your Endpoint URL

1. Once the endpoint is created, click on it to open its detail page.
2. Look for the **HTTP Endpoint** field. It will look something like:

   ```
   https://abc123def456-11434.proxy.runpod.net
   ```

   Copy this URL — you'll need it in Step 6.

   The number `11434` is the Ollama port. The URL format is always:
   `https://YOUR-ENDPOINT-ID-11434.proxy.runpod.net`

---

## Step 5 — Pull a Model

Before you can use a model, you need to download it to your volume.

1. On the endpoint detail page, click **Connect** or **Send Request**.
2. You need to send a request to pull the model. Use this format in the RunPod
   console or with curl:

   ```
   POST https://YOUR-ENDPOINT-ID-11434.proxy.runpod.net/api/pull
   Body: { "name": "llama3.3:70b" }
   ```

   Replace `llama3.3:70b` with the model you want. You can browse available models
   at [ollama.com/library](https://ollama.com/library).

   Common models for LLM Council:
   - `llama3.3:70b` — Excellent all-around, requires 80 GB VRAM
   - `llama3.1:8b` — Fast and efficient, 24 GB VRAM
   - `qwen2.5:72b` — Strong at coding and analysis, 80 GB VRAM
   - `mistral:7b` — Fast, good for the summarization role

3. The pull can take several minutes. Once done, the model is saved to your
   network volume and won't need to be downloaded again.

---

## Step 6 — Add the Model to LLM Council

1. Open LLM Council in your browser and click the gear icon (⚙) to open Settings.
2. Click the **Models** tab, then **+ Add Model**.
3. Fill in the fields:

   - **Display name:** Whatever you want to call it (e.g. "Llama 70B (RunPod)")
   - **Model ID:** The exact model name as used in Ollama (e.g. `llama3.3:70b`)
   - **API Base URL:** Your endpoint URL from Step 4, with `/v1` appended:
     ```
     https://abc123def456-11434.proxy.runpod.net/v1
     ```
   - **API Key:** Leave this **blank**. RunPod serverless endpoints don't use an API key.

4. Click **Test Connection**. If the endpoint is awake, you'll see a green checkmark.
   If it's asleep, click **Wake Up Models** at the top of a conversation first, wait
   30–90 seconds, then try again.

5. Click **Save Settings**.

---

## Using the Wake Up Button

RunPod serverless endpoints sleep when idle. Before starting a conversation with a
RunPod model, you may need to wake it up first.

At the top of every conversation, LLM Council shows a **Wake Up Models** button when
your council includes any RunPod models. The button has three states:

- **Red** — The endpoint is asleep or unreachable. Click to send a wake-up request.
- **Yellow (flashing)** — Warming up. Wait 30–90 seconds.
- **Green** — The endpoint is awake and ready.

If the button turns back to red after warming up, check that your endpoint URL is
correct in Settings and that your RunPod account has credit available.

---

## Costs and Tips

- RunPod charges only when a worker is active (processing a request or warming up).
  With Min Workers = 0, you pay nothing when the endpoint is idle.
- The first request after a sleep period takes 30–90 seconds while the GPU starts up.
  Subsequent requests are fast.
- If you find yourself using a model constantly, consider setting Min Workers to 1 to
  keep it always warm — but this means continuous billing.
- Large models (70B) cost more per hour but often give better results. For the
  Chairman role especially, a larger model is worth the cost.

---

## Troubleshooting

**"Test Connection" fails even after waking up**
- Double-check the URL format: `https://ENDPOINT-11434.proxy.runpod.net/v1` (note the `/v1`)
- Make sure you left the API Key field blank
- Check the RunPod dashboard to confirm the endpoint is active and has no errors

**Model not found after pulling**
- Make sure you set the `OLLAMA_MODELS=/runpod-volume/ollama` environment variable
  when creating the endpoint. Without it, models are stored in temporary storage and
  disappear when the pod sleeps.

**Endpoint keeps failing**
- Check your RunPod account balance — endpoints stop working when you run out of credit
- Try redeploying the endpoint from the RunPod dashboard

**Can I use RunPod for the Chairman role?**
Yes. RunPod models work the same as any other model in LLM Council. A large model
like Llama 3.3 70B makes an excellent Chairman.
