"""Order handling: product catalog + Stripe Checkout sessions + webhook persistence."""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Optional

import stripe

DATA_DIR = Path(__file__).parent / "data"
DB_PATH = Path(__file__).parent.parent / "orders.db"

_products: list[dict] = []


def load_products() -> None:
    global _products
    with open(DATA_DIR / "products.json", "r", encoding="utf-8") as f:
        _products = json.load(f)
    print(f"[orders] loaded {len(_products)} products")


def list_products() -> list[dict]:
    return _products


def find_product(product_id_or_name: str) -> Optional[dict]:
    """Match by id (exact) or name (case-insensitive substring)."""
    q = product_id_or_name.strip().lower()
    for p in _products:
        if p["id"].lower() == q:
            return p
    for p in _products:
        if q in p["name"].lower():
            return p
    return None


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stripe_session_id TEXT UNIQUE,
            product_id TEXT,
            product_name TEXT,
            quantity INTEGER,
            amount_total INTEGER,
            currency TEXT,
            customer_email TEXT,
            status TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


def record_paid_order(session: dict) -> None:
    md = session.get("metadata") or {}
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        INSERT OR REPLACE INTO orders
            (stripe_session_id, product_id, product_name, quantity,
             amount_total, currency, customer_email, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session.get("id"),
            md.get("product_id"),
            md.get("product_name"),
            int(md.get("quantity", 1)),
            session.get("amount_total"),
            session.get("currency"),
            (session.get("customer_details") or {}).get("email")
            or session.get("customer_email"),
            "paid",
        ),
    )
    conn.commit()
    conn.close()


def create_checkout_session(
    product_id: str,
    quantity: int,
    customer_email: Optional[str] = None,
) -> dict:
    """Create a Stripe Checkout session and return {url, session_id, ...}."""
    stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
    base = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")

    product = find_product(product_id)
    if not product:
        raise ValueError(f"Unknown product: {product_id}")
    if quantity < 1 or quantity > 50:
        raise ValueError("Quantity must be between 1 and 50.")

    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[
            {
                "price_data": {
                    "currency": product["currency"],
                    "product_data": {
                        "name": product["name"],
                        "description": product["description"],
                    },
                    "unit_amount": product["price_cents"],
                },
                "quantity": quantity,
            }
        ],
        success_url=f"{base}/?paid=1&session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{base}/?canceled=1",
        customer_email=customer_email,
        metadata={
            "product_id": product["id"],
            "product_name": product["name"],
            "quantity": str(quantity),
        },
    )
    return {
        "url": session.url,
        "session_id": session.id,
        "amount_total_cents": product["price_cents"] * quantity,
        "currency": product["currency"],
        "product_name": product["name"],
        "quantity": quantity,
    }
