"""
Intentionally buggy Python code for testing the AI reviewer.
This file contains:
  - Division by zero risk
  - SQL injection vulnerability
  - Hardcoded credentials
  - Mutable default argument bug
  - Missing error handling
  - Inefficient loop
  - Unused variable
"""

import os


# ── Bug 1: Division by zero (no check) ───────────────────────
def calculate_average(numbers):
    total = sum(numbers)
    return total / len(numbers)          # crashes if numbers is empty


# ── Bug 2: SQL Injection ──────────────────────────────────────
def get_user_by_name(name):
    query = f"SELECT * FROM users WHERE name = '{name}'"
    # An attacker can pass: name = "'; DROP TABLE users; --"
    return query


# ── Bug 3: Hardcoded credentials ─────────────────────────────
DB_PASSWORD = "admin123"
API_SECRET  = "super-secret-key-do-not-share"

def connect_to_database():
    host     = "localhost"
    user     = "root"
    password = "admin123"              # hardcoded password
    return f"Connected as {user}"


# ── Bug 4: Mutable default argument ──────────────────────────
def add_item(item, cart=[]):           # shared state across calls!
    cart.append(item)
    return cart


# ── Bug 5: Missing error handling ────────────────────────────
def read_config(filepath):
    with open(filepath) as f:          # crashes if file doesn't exist
        return f.read()


# ── Bug 6: Inefficient string concatenation in loop ──────────
def build_report(rows):
    report = ""
    for row in rows:
        report += str(row) + "\n"      # O(n²) — should use join()
    return report


# ── Bug 7: Catching bare Exception (hides real errors) ───────
def parse_number(value):
    try:
        return int(value)
    except:                            # bare except catches everything
        return 0


# ── Bug 8: Unused variable (dead code) ───────────────────────
def calculate_discount(price, percent):
    tax_rate   = 0.18                  # calculated but never used
    discount   = price * (percent / 100)
    final_price = price - discount
    return final_price