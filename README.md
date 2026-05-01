# Retail Brand Chatbot — FastAPI + OpenAI + Stripe

A production-ready starter for a retail brand chatbot that:

- **Answers FAQs** with RAG (OpenAI embeddings + cosine similarity over your `faqs.json`)
- **Books real orders** via Stripe Checkout (test or live mode)
- Ships with a clean built-in chat UI at `/`
- One-click deploys free on Render

Built with FastAPI, OpenAI, Stripe, NumPy. ~600 lines total.

---

## Quickstart (local)

```bash
# 1. Clone / unzip, then:
cd retail-chatbot
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Copy env template and fill in keys
cp .env.example .env
# edit .env: OPENAI_API_KEY, STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET

# 3. Run
uvicorn app.main:app --reload
```

Open http://localhost:8000

To test Stripe webhooks locally:
```bash
stripe listen --forward-to localhost:8000/api/stripe/webhook
# Use the whsec_... it prints as STRIPE_WEBHOOK_SECRET in your .env
```

---

## Deploying free on Render

Render's free tier is perfect for this app. Free web services sleep after
~15 minutes of inactivity (cold start ≈ 30 s on next request) and the local
SQLite `orders.db` resets on redeploys. For real production traffic, switch
to Render's free Postgres add-on.

### 1. Get your API keys

- **OpenAI**: https://platform.openai.com/api-keys → create a key (`sk-...`)
- **Stripe**:
  - https://dashboard.stripe.com/test/apikeys → copy **Secret key** (`sk_test_...`)
  - You'll add the webhook secret in step 5 below.

### 2. Push this folder to GitHub

```bash
git init
git add .
git commit -m "Initial retail chatbot"
git branch -M main
git remote add origin https://github.com/<you>/retail-chatbot.git
git push -u origin main
```

### 3. Create the Render service

1. Go to https://dashboard.render.com → **New +** → **Web Service**
2. Connect the GitHub repo
3. Render auto-detects `render.yaml` — accept the defaults
4. Plan: **Free**
5. Click **Create Web Service**

The first build takes a few minutes. Render will give you a URL like
`https://retail-chatbot-xyz.onrender.com`.

### 4. Set environment variables

In Render → your service → **Environment**, set:

| Key                    | Value                                                   |
|------------------------|---------------------------------------------------------|
| `OPENAI_API_KEY`       | your `sk-...`                                           |
| `STRIPE_SECRET_KEY`    | your `sk_test_...` (or `sk_live_...` when ready)        |
| `STRIPE_WEBHOOK_SECRET`| filled in step 5                                        |
| `PUBLIC_BASE_URL`      | `https://retail-chatbot-xyz.onrender.com` (no trailing /) |
| `OPENAI_MODEL`         | `gpt-4o-mini` (default; change if you want)             |
| `EMBEDDING_MODEL`      | `text-embedding-3-small` (default)                      |

Click **Save, rebuild, and deploy**.

### 5. Register the Stripe webhook

1. https://dashboard.stripe.com/test/webhooks → **Add endpoint**
2. Endpoint URL: `https://retail-chatbot-xyz.onrender.com/api/stripe/webhook`
3. Events to send: `checkout.session.completed`
4. Click **Add endpoint**, then reveal the **Signing secret** (`whsec_...`)
5. Paste it back in Render as `STRIPE_WEBHOOK_SECRET` and redeploy

You're live. Visit your Render URL and start chatting.

---

## Customizing for your brand

| File                       | What to change                                  |
|----------------------------|--------------------------------------------------|
| `app/data/faqs.json`       | Your real FAQs. Embeddings re-build on startup. |
| `app/data/products.json`   | Your real catalog (price in cents).             |
| `app/llm.py` `SYSTEM_PROMPT` | Tone of voice, brand name, support email.     |
| `static/index.html` / `style.css` | Logo, colors, copy.                       |

Tip: for hundreds of FAQs, swap the in-memory NumPy index for a real vector
DB (Pinecone, pgvector, Qdrant). The interface in `app/rag.py` is small and
easy to swap.

---

## Architecture

```
Browser (static/index.html + chat.js)
    │  POST /api/chat  { messages: [...] }
    ▼
FastAPI (app/main.py)
    │
    ▼
llm.run_chat()  ── OpenAI Chat Completions with tools
    │              ├─ search_faq  → rag.search_as_text() [embeddings + cosine]
    │              └─ create_order → orders.create_checkout_session() [Stripe]
    ▼
Reply + optional payment_url

Stripe → POST /api/stripe/webhook (checkout.session.completed)
       → orders.record_paid_order() → SQLite orders.db
```

---

## Endpoints

- `GET  /`                       — chat UI
- `POST /api/chat`               — `{ messages: [{role, content}, ...] }` → `{ reply, payment_url? }`
- `GET  /api/products`           — catalog JSON
- `POST /api/stripe/webhook`     — Stripe events
- `GET  /healthz`                — health check
- `GET  /docs`                   — auto OpenAPI docs

---

## Going to production

- Switch `STRIPE_SECRET_KEY` to `sk_live_...` and update the webhook secret
- Replace SQLite with Render Postgres (free tier) — see `app/orders.py`
- Add a paid Render plan to avoid cold starts
- Rate-limit `/api/chat` (e.g. with `slowapi`) to control OpenAI spend
- Add a moderation pass (OpenAI Moderation API) on user input
- Persist conversation history in a DB if you need multi-session memory

---

## License

MIT. Ship it.
