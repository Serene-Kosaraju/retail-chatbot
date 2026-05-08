"""FastAPI app: serves chat UI, /api/chat, and Stripe webhook."""
from __future__ import annotations

import os
# from contextlib import asynccontextmanager
from pathlib import Path

# import stripe
import json
from flask import Flask, render_template, request, jsonify
from groq import Groq

app = Flask(__name__)

# from .schemas import ChatRequest, ChatResponse

# load_dotenv()

# STATIC_DIR = Path(__file__).parent.parent / "static"

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

def get_faq_context():
    global _faqs, _matrix
    with open(DATA_DIR / "faqs.json", "r", encoding="utf-8") as f:
        _faqs = json.load(f)
    if not _faqs:
        _matrix = np.zeros((0, 1), dtype=np.float32)
        return
    texts = "\n".join([f"Q: {item['q']}\nA: {item['a']}" for item in _faqs['faqs']])
    _matrix = _embed(texts)
    print(f"[rag] embedded {len(_faqs)} FAQ entries")
    return texts
    return "\n".join([f"Q: {item['q']}\nA: {item['a']}" for item in faq_data['faqs']])

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/chat", methods=["POST"])
def chat():
    user_message = request.json["message"]
    # if not req.messages:
    #     raise HTTPException(status_code=400, detail="messages must not be empty")
    # if not os.getenv("GROQ_API_KEY"):
    #     raise HTTPException(status_code=500, detail="GROQ_API_KEY is not configured")

    # history = [m.model_dump() for m in req.messages]
    context = get_faq_context()

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


# @app.route("/api/products", methods=["GET"])
# async def products() -> list[dict]:
#     return orders.list_products()


# @app.route("/api/stripe/webhook", methods = ["POST"])
# async def stripe_webhook(request: Request) -> JSONResponse:
#     payload = await request.body()
#     sig = request.headers.get("stripe-signature", "")
#     secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
#     if not secret:
#         raise HTTPException(status_code=500, detail="STRIPE_WEBHOOK_SECRET not set")
#     try:
#         event = stripe.Webhook.construct_event(payload, sig, secret)
#     except (ValueError, stripe.error.SignatureVerificationError) as e:
#         raise HTTPException(status_code=400, detail=f"Invalid webhook: {e}") from e

#     if event["type"] == "checkout.session.completed":
#         session = event["data"]["object"]
#         try:
#             orders.record_paid_order(session)
#             print(f"[webhook] recorded paid order {session.get('id')}")
#         except Exception as e:  # noqa: BLE001
#             print(f"[webhook] failed to record order: {e}")

#     return JSONResponse({"received": True})


# @app.get("/healthz")
# async def healthz() -> dict:
#     return {"ok": True}


# # Mount static frontend at root (index.html, style.css, chat.js)
# app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
