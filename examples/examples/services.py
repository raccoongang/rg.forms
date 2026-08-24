"""Deterministic, clearly-labeled fake "database" services for the examples.

None of this is a real datastore — it stands in for the queries a production app
would run (``User.objects.filter(...).exists()``, a coupon lookup, a plan/feature
gate, a product catalog). Everything is deterministic so the example tests are
fast and reproducible. The optional ``latency`` argument simulates DB round-trip
time for the incremental-validation demo; it defaults to ``0.0`` so tests never
sleep — the demo view passes a small non-zero value only to make the pending
indicator visible in a browser.
"""

from __future__ import annotations

import time

# --- Account registration / onboarding -------------------------------------
TAKEN_USERNAMES = {"admin", "root", "test", "user", "demo", "alice", "bob", "support"}
REGISTERED_EMAILS = {"taken@example.com", "admin@acme.co"}
FREE_EMAIL_DOMAINS = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "mail.com"}

# --- Coupons ----------------------------------------------------------------
VALID_COUPONS = {
    "WELCOME10": {"discount": 10, "description": "10% off for new users"},
    "SAVE20": {"discount": 20, "description": "20% off seasonal sale"},
    "LAUNCH50": {"discount": 50, "description": "50% off launch special"},
}

# --- Product catalog (cascading + order configurator) -----------------------
CATEGORIES = [
    {"id": 1, "name": "Electronics"},
    {"id": 2, "name": "Clothing"},
    {"id": 3, "name": "Books"},
]

PRODUCTS = [
    {"id": 101, "category_id": 1, "name": "Laptop", "price": "999.99"},
    {"id": 102, "category_id": 1, "name": "Smartphone", "price": "699.99"},
    {"id": 103, "category_id": 1, "name": "Headphones", "price": "149.99"},
    {"id": 201, "category_id": 2, "name": "T-Shirt", "price": "29.99"},
    {"id": 202, "category_id": 2, "name": "Jeans", "price": "79.99"},
    {"id": 203, "category_id": 2, "name": "Jacket", "price": "129.99"},
    {"id": 301, "category_id": 3, "name": "Python Guide", "price": "49.99"},
    {"id": 302, "category_id": 3, "name": "Django Manual", "price": "39.99"},
    {"id": 303, "category_id": 3, "name": "Web Development", "price": "59.99"},
]

# --- Plan tiers (order configurator) ----------------------------------------
# code is intentionally a numeric-looking string with a leading zero to
# demonstrate strict canonical string semantics ("001" stays "001").
PLANS = [
    {"code": "001", "name": "Starter", "unit_price": "9.00"},
    {"code": "010", "name": "Team", "unit_price": "29.00"},
    {"code": "100", "name": "Enterprise", "unit_price": "99.00"},
]


def username_is_taken(username: str, *, latency: float = 0.0) -> bool:
    """Simulate ``User.objects.filter(username=...).exists()``."""
    if latency:
        time.sleep(latency)
    return username.strip().lower() in TAKEN_USERNAMES


def email_is_registered(email: str, *, latency: float = 0.0) -> bool:
    """Simulate an email-uniqueness lookup."""
    if latency:
        time.sleep(latency)
    return email.strip().lower() in REGISTERED_EMAILS


def is_free_email_domain(email: str) -> bool:
    domain = email.rsplit("@", 1)[-1].lower() if "@" in email else ""
    return domain in FREE_EMAIL_DOMAINS


def lookup_coupon(code: str) -> dict | None:
    return VALID_COUPONS.get(code.strip().upper())


def get_categories():
    return CATEGORIES


def get_products_for_category(category_id):
    if not category_id:
        return []
    category_id = int(category_id)
    return [p for p in PRODUCTS if p["category_id"] == category_id]


def get_product_by_id(product_id):
    if not product_id:
        return None
    product_id = int(product_id)
    for product in PRODUCTS:
        if product["id"] == product_id:
            return product
    return None


def get_plans():
    return PLANS


def get_plan(code: str) -> dict | None:
    for plan in PLANS:
        if plan["code"] == code:
            return plan
    return None
