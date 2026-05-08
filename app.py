import os
import json
from flask import Flask, render_template, request, jsonify
from groq import Groq

app = Flask(__name__)
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# Load FAQ data
with open('faq_data.json', 'r') as f:
    faq_data = json.load(f)

def get_faq_context():
    return "\n".join([f"Q: {item['q']}\nA: {item['a']}" for item in faq_data['faqs']])

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json["message"]
    context = get_faq_context()
    
    # System prompt forces the bot to use the FAQ
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
