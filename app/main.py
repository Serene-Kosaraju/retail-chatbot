"""FastAPI app: serves chat UI, /api/chat, and Stripe webhook."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

import stripe
import groq
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import llm, orders, rag
from .schemas import ChatRequest, ChatResponse

load_dotenv()

STATIC_DIR = Path(__file__).parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    orders.load_products()
    orders.init_db()
    try:
        rag.load_faqs()
    except Exception as e:  # noqa: BLE001
        print(f"[startup] FAQ embedding failed: {e}. Chat will still work without RAG.")
    yield


app = FastAPI(title="Retail Chatbot", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    if not req.messages:
        raise HTTPException(status_code=400, detail="messages must not be empty")
    if not os.getenv("GROQ_API_KEY"):
        raise HTTPException(status_code=500, detail="GROQ_API_KEY is not configured")

    history = [m.model_dump() for m in req.messages]
    user_message = req.json["message"]
    context = rag.load_faqs()

    system_prompt = f"You are a helpful support bot. Use this FAQ data to answer questions:\n{context}\nIf the answer is not in the FAQ, say you don't know."
    completion = client.chat.completions.create(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        model="llama3-8b-8192",
    )
    return jsonify({"response": completion.choices[0].message.content})
    # try:
    #     result = llm.run_chat(history)
    # except Exception as e:  # noqa: BLE001
    #     print(f"[chat] error: {e}")
    #     raise HTTPException(status_code=500, detail=f"Chat error: {e}") from e
    # return ChatResponse(**result)


@app.get("/api/products")
async def products() -> list[dict]:
    return orders.list_products()


@app.post("/api/stripe/webhook")
async def stripe_webhook(request: Request) -> JSONResponse:
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
    if not secret:
        raise HTTPException(status_code=500, detail="STRIPE_WEBHOOK_SECRET not set")
    try:
        event = stripe.Webhook.construct_event(payload, sig, secret)
    except (ValueError, stripe.error.SignatureVerificationError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid webhook: {e}") from e

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        try:
            orders.record_paid_order(session)
            print(f"[webhook] recorded paid order {session.get('id')}")
        except Exception as e:  # noqa: BLE001
            print(f"[webhook] failed to record order: {e}")

    return JSONResponse({"received": True})


@app.get("/healthz")
async def healthz() -> dict:
    return {"ok": True}


# Mount static frontend at root (index.html, style.css, chat.js)
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
