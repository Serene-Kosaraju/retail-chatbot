"""FastAPI app: serves chat UI, /api/chat, and Stripe webhook."""

import os
from pathlib import Path

import json
from flask import Flask, render_template, request, jsonify
from groq import Groq

app = Flask(__name__)


DATA_DIR = Path(__file__).parent / "data"
_faqs: List[dict] = []
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

def get_faq_context():
    global _faqs
    with open(DATA_DIR / "faqs.json", "r", encoding="utf-8") as f:
        _faqs = json.load(f)
    if not _faqs:
        return
    texts = "\n".join([f"Q: {item['q']}\nA: {item['a']}" for item in _faqs['faqs']])
    return texts

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/chat", methods=["POST"])
def chat():
    user_message = request.json["message"]
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
