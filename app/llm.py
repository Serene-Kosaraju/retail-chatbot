"""OpenAI chat orchestration with tool calling for FAQ search and order creation."""
from __future__ import annotations

import json
import os
from typing import Any

from groq import Groq

from . import orders, rag

MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

SYSTEM_PROMPT = """You are a friendly retail brand assistant for an apparel store.

You help customers in two ways:
1. ANSWER QUESTIONS about shipping, returns, sizing, payment methods, store
   policies, etc. Use the `search_faq` tool to look up accurate, up-to-date
   answers from our knowledge base. Quote it faithfully — never invent policies.
2. BOOK ORDERS. If the customer wants to buy something, gather:
     - product (name or id from the catalog)
     - quantity (default 1 if unstated)
     - email for the receipt
   Then call `create_order` to generate a secure Stripe payment link.
   Confirm the product name and total price back to the customer, then share
   the link and tell them their order will be confirmed once payment completes.

Available products (always pick from this list):
{product_list}

Rules:
- Be concise, warm, and on-brand. No emojis unless the user uses them first.
- If a question is outside FAQs and not about ordering, politely say you'll
  pass it to human support at support@brand.example.
- Never make up prices, policies, or stock. If unsure, search_faq or say so.
- Show prices in dollars (e.g. "$29.00"), not cents.
"""


def _system_prompt() -> str:
    lines = []
    for p in orders.list_products():
        price = f"${p['price_cents'] / 100:.2f}"
        lines.append(f"- {p['id']} | {p['name']} | {price} — {p['description']}")
    return SYSTEM_PROMPT.format(product_list="\n".join(lines))


TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_faq",
            "description": (
                "Search the brand's FAQ knowledge base for relevant answers. "
                "Use this for any question about shipping, returns, sizing, "
                "payment, hours, loyalty program, gift cards, etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The customer's question, restated clearly.",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_order",
            "description": (
                "Create a Stripe Checkout payment link for a product order. "
                "Only call after you have a product (from the catalog), quantity, "
                "and customer email."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "string",
                        "description": "Product id or name from the catalog.",
                    },
                    "quantity": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 50,
                    },
                    "customer_email": {
                        "type": "string",
                        "description": "Customer's email for the receipt.",
                    },
                },
                "required": ["product_id", "quantity", "customer_email"],
            },
        },
    },
]


def _client() -> Groq:
    return Groq()


def run_chat(history: list[dict]) -> dict:
    """Run a tool-using chat turn. Returns {reply, payment_url}."""
    messages: list[dict] = [{"role": "system", "content": _system_prompt()}]
    messages.extend(history)

    payment_url: str | None = None
    client = _client()

    # Allow up to 4 tool-call rounds before forcing a final answer.
    for _ in range(4):
        resp = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.4,
        )
        msg = resp.choices[0].message
        tool_calls = msg.tool_calls or []

        if not tool_calls:
            return {"reply": msg.content or "", "payment_url": payment_url}

        # Append assistant message that includes the tool calls
        messages.append(
            {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tool_calls
                ],
            }
        )

        for tc in tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            if name == "search_faq":
                result = rag.search_as_text(args.get("query", ""))
            elif name == "create_order":
                try:
                    order = orders.create_checkout_session(
                        product_id=args["product_id"],
                        quantity=int(args.get("quantity", 1)),
                        customer_email=args.get("customer_email"),
                    )
                    payment_url = order["url"]
                    total = order["amount_total_cents"] / 100
                    result = (
                        f"Checkout created. Product: {order['product_name']}, "
                        f"Quantity: {order['quantity']}, "
                        f"Total: ${total:.2f} {order['currency'].upper()}. "
                        f"Payment URL: {order['url']}"
                    )
                except Exception as e:  # noqa: BLE001
                    result = f"ERROR creating order: {e}"
            else:
                result = f"Unknown tool: {name}"

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                }
            )

    # Fallback if model kept calling tools
    return {
        "reply": "Sorry, I'm having trouble completing that request. Please try again.",
        "payment_url": payment_url,
    }
