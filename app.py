
# app.py
# Experience Cards – FULL DEMO VERSION
# Canada + USA demo cards (15 each)
# Safe to REPLACE your existing app.py entirely for demo purposes

import re
import math
import sqlite3
import logging
from datetime import datetime
from collections import Counter
from typing import List, Dict, Any

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

# ----------------------------
# Logging
# ----------------------------
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("experience-cards")

# ----------------------------
# App
# ----------------------------
app = FastAPI(title="Experience Cards Demo", version="1.5.0")
DB_PATH = "demo.db"

# ----------------------------
# Guardrails
# ----------------------------
BANNED_KEYWORDS = [
    "kill", "suicide", "bomb", "terror", "nazi",
    "send me your otp", "share your otp", "password",
]

MIN_EXPERIENCE_STRUCTURE_SCORE = 3

# ----------------------------
# DB helpers
# ----------------------------
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS experiences (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        category TEXT,
        tags TEXT,
        content TEXT,
        content_lang TEXT,
        created_at TEXT
    )
    """)
    conn.commit()
    conn.close()

init_db()

# ----------------------------
# Seed (Canada + USA)
# ----------------------------
def seed_if_empty():
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as c FROM experiences")
    if int(cur.fetchone()["c"]) > 0:
        conn.close()
        return

    now = datetime.utcnow().isoformat()
    cards = []

    # CANADA (15)
    cards += [
        ("Newcomer account opening","Onboarding","canada,newcomer,account",
         "I moved to Canada and opened a bank account with my passport and temporary address. The bank explained newcomer programs and limits.","en",now),
        ("SIN not ready","Onboarding","sin,canada",
         "I did not have my SIN yet. The bank allowed a basic account and explained that limits would change after SIN update.","en",now),
        ("Temporary address","Onboarding","address,canada",
         "I used a temporary address to open my account and updated it later after moving.","en",now),
        ("Mobile banking setup","Digital","mobile,2fa",
         "I installed the official app, enabled two-factor authentication, and avoided public Wi-Fi.","en",now),
        ("Forgot password","Digital","password,reset",
         "After resetting my password, I waited for the lock to clear and enabled security alerts.","en",now),
        ("Language help","Digital","language,branch",
         "Branch staff helped me understand the app features in simple language.","en",now),
        ("Debit vs credit","Cards","debit,credit",
         "Debit cards are for spending, credit cards help build credit history.","en",now),
        ("Card declined","Cards","declined,limit",
         "My card was declined due to a daily limit which I adjusted in the app.","en",now),
        ("Contactless limits","Cards","tap,contactless",
         "I learned tap payments have limits and can be disabled if needed.","en",now),
        ("CRA scam call","Fraud","cra,scam",
         "A call claimed to be CRA. I verified through official sources and reported it.","en",now),
        ("Phishing email","Fraud","email,phishing",
         "I avoided clicking a suspicious email link and checked my account only via the app.","en",now),
        ("Account frozen","Security","frozen,security",
         "My account was frozen after unusual activity and restored after verification.","en",now),
        ("E-transfer delay","Transfers","etransfer,delay",
         "An Interac transfer was delayed due to security checks.","en",now),
        ("Overdraft confusion","Fees","overdraft,fees",
         "I learned how overdraft fees work and enabled balance alerts.","en",now),
        ("Monthly fees","Fees","monthly,fees",
         "I switched to an account with a fee waiver after reviewing conditions.","en",now),
    ]

    # USA (15)
    cards += [
        ("Opening US account","Onboarding","usa,account",
         "I opened a US bank account with ID and address.","en",now),
        ("No SSN yet","Onboarding","ssn,itin",
         "Without SSN, the bank explained ITIN-based options.","en",now),
        ("Online vs branch","Onboarding","online,branch",
         "Branch opening resolved verification issues faster.","en",now),
        ("App login issue","Digital","login,device",
         "A new device required extra verification.","en",now),
        ("Two-factor auth","Digital","2fa,security",
         "Two-factor authentication protected my account.","en",now),
        ("Shared device risk","Digital","shared,device",
         "Sharing devices increased security risk so I used profiles.","en",now),
        ("Debit declined","Cards","debit,declined",
         "Debit was declined due to insufficient funds.","en",now),
        ("First credit card","Cards","credit,score",
         "I used a secured card to build credit score.","en",now),
        ("Online shopping","Cards","online,shopping",
         "Virtual cards improved online payment safety.","en",now),
        ("IRS scam call","Fraud","irs,scam",
         "A call claiming IRS was confirmed as scam.","en",now),
        ("Zelle warning","Fraud","zelle,scam",
         "Zelle payments are hard to reverse and should be used carefully.","en",now),
        ("Account locked","Security","locked,login",
         "Account locked after failed logins and restored after verification.","en",now),
        ("Overdraft fees","Fees","overdraft,fees",
         "Overdraft fees were charged and explained by the bank.","en",now),
        ("Bank statements","Statements","pending,posted",
         "I learned the difference between pending and posted transactions.","en",now),
        ("Customer support","Support","support,branch",
         "Some issues are better resolved in branch than by phone.","en",now),
    ]

    cur.executemany(
        "INSERT INTO experiences (title,category,tags,content,content_lang,created_at) VALUES (?,?,?,?,?,?)",
        cards
    )
    conn.commit()
    conn.close()

seed_if_empty()

# ----------------------------
# Simple matching
# ----------------------------
def tokenize(text):
    return re.findall(r"[a-z0-9]{2,}", text.lower())

def ask_score(q, c):
    qs = Counter(tokenize(q))
    cs = Counter(tokenize(c))
    inter = sum((qs & cs).values())
    return inter

@app.post("/ask")
def ask(payload: Dict[str, Any]):
    q = payload.get("question","")
    if len(q) < 8:
        raise HTTPException(400,"Question too short")

    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM experiences")
    rows = cur.fetchall()
    conn.close()

    scored = []
    for r in rows:
        s = ask_score(q, r["content"])
        if s > 0:
            scored.append({
                "title": r["title"],
                "category": r["category"],
                "tags": r["tags"],
                "content": r["content"],
                "score": s
            })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return {"matches": scored[:5]}

@app.get("/", response_class=HTMLResponse)
def home():
    return "<h2>Experience Cards Demo is running</h2><p>Use POST /ask</p>"
