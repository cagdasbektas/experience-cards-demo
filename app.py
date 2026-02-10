# app.py
# Experience Cards (FastAPI + SQLite)
# UI languages:
#   - Canada: English + French
#   - US: English + Spanish
# NOTE: UI-only multilingual. No auto-translation, no multilingual NLP.

import re
import math
import sqlite3
import logging
from datetime import datetime
from collections import Counter
from typing import List, Tuple, Dict, Any

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

# ----------------------------
# Logging
# ----------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("experience-cards")

# ----------------------------
# App
# ----------------------------
app = FastAPI(title="Experience Cards", version="1.4.1")

DB_PATH = "demo.db"

# ----------------------------
# Guardrails (config)
# ----------------------------
BANNED_KEYWORDS = [
    # violence / self-harm / explosives (keep conservative)
    "kill", "suicide", "bomb", "terror", "nazi",
    # scam / credential harvesting phrases
    "send me your otp", "share your otp", "give me your password", "bank password",
    # explicit
    "nudes", "sex",
]

ALLOWED_DOMAINS = [
    # public info domains (sample allowlist)
    "canada.ca",
    "fcac-acfc.gc.ca",
    "cba.ca",
    "consumerfinance.gov",
    "ftc.gov",
    "usa.gov",
    "fca.org.uk",
]

MIN_EXPERIENCE_STRUCTURE_SCORE = 4  # keep conservative

# ----------------------------
# Simple i18n (UI only)
# ----------------------------
I18N: Dict[str, Dict[str, str]] = {
    "en": {
        "app_title": "Experience Cards",
        "app_title_demo": "Experience Cards Demo",
        "subtitle": "Safety-first, explainable support for digital banking (retrieval-only)",
        "region_label": "Region",
        "region_ca": "Canada",
        "region_us": "United States",
        "language_label": "Language",
        "ask_title": "Ask a question",
        "ask_hint": "Describe your digital banking issue (no personal data).",
        "ask_placeholder": "Example: My transfer is pending / I cannot log in / I received a suspicious message...",
        "ask_button": "Submit",
        "results_title": "Matching Experience Cards",
        "no_results": "No relevant cards found for this question.",
        "why_this_match": "Why this match",
        "score": "Score",
        "category": "Category",
        "tags": "Tags",
        "admin_link": "Admin",
        "cards_link": "Browse Cards",
        "admin_title": "Admin – Add Experience Card",
        "admin_subtitle": "Add finance-only experiences. Safety checks apply.",
        "field_title": "Title",
        "field_category": "Category",
        "field_tags": "Tags (comma-separated, English tags recommended)",
        "field_language": "Content Language",
        "field_content": "Experience Content",
        "save_button": "Save",
        "back_home": "Back to Home",
        "presentation_on": "Presentation mode is ON",
        "presentation_tip": "Tip: Use concise questions and show explainability.",
        "error_prefix": "Error",
        "guardrail_rejected": "Submission rejected by safety checks.",
        "guardrail_hint": "Please remove personal data, disallowed links, or unsafe wording.",
        "question_too_short": "Please provide a longer question.",
        "footer_note": "This demo does not provide financial advice and does not make decisions.",
        "audit_note": "Audit & moderation logs exist server-side and are intentionally not exposed in the user interface.",
        "lang_en": "English",
        "lang_fr": "French",
        "lang_es": "Spanish",
        "pill_safe": "SAFETY-FIRST",
        "pill_retrieval": "RETRIEVAL-ONLY",
        "pill_demo": "DEMO",
        "latest_cards": "Latest Cards",
        "no_cards_yet": "No cards yet.",
        "safety_title": "Safety & Compliance (Demo Guardrails)",
        "safety_points": "No advice • No decisions • Retrieval-only • PII checks • Domain allowlist • Logs/audit trail",
        "banned_kw": "Banned keywords",
        "allowed_domains": "Allowed domains (links inside cards)",
        "min_score": "Min structure score",
        "seed_note": "If the database is empty, the app auto-loads a small set of sample finance cards.",
        "cards_title": "All Experience Cards",
        "cards_subtitle": "For demo review. In production, access controls would apply.",
        "sponsor_badge": "SPONSOR",
        "sponsor_top": "Placeholder: partner message area (no tracking).",
        "sponsor_card": "Placeholder: sponsored slot (demo-only, no tracking).",
    },
    "fr": {
        "app_title": "Cartes d’Expérience",
        "app_title_demo": "Démo de Cartes d’Expérience",
        "subtitle": "Assistance explicable et prudente pour la banque numérique (recherche uniquement)",
        "region_label": "Région",
        "region_ca": "Canada",
        "region_us": "États-Unis",
        "language_label": "Langue",
        "ask_title": "Poser une question",
        "ask_hint": "Décrivez votre problème de banque numérique (sans données personnelles).",
        "ask_placeholder": "Exemple : Mon virement est en attente / Je n’arrive pas à me connecter / J’ai reçu un message suspect...",
        "ask_button": "Soumettre",
        "results_title": "Cartes d’Expérience correspondantes",
        "no_results": "Aucune carte pertinente n’a été trouvée pour cette question.",
        "why_this_match": "Pourquoi cette correspondance",
        "score": "Score",
        "category": "Catégorie",
        "tags": "Étiquettes",
        "admin_link": "Admin",
        "cards_link": "Voir les cartes",
        "admin_title": "Admin – Ajouter une Carte d’Expérience",
        "admin_subtitle": "Ajoutez des expériences financières uniquement. Des contrôles de sécurité s’appliquent.",
        "field_title": "Titre",
        "field_category": "Catégorie",
        "field_tags": "Étiquettes (séparées par des virgules, étiquettes en anglais recommandées)",
        "field_language": "Langue du contenu",
        "field_content": "Contenu de l’expérience",
        "save_button": "Enregistrer",
        "back_home": "Retour à l’accueil",
        "presentation_on": "Mode présentation ACTIVÉ",
        "presentation_tip": "Astuce : utilisez des questions concises et montrez l’explicabilité.",
        "error_prefix": "Erreur",
        "guardrail_rejected": "Soumission rejetée par les contrôles de sécurité.",
        "guardrail_hint": "Veuillez supprimer les données personnelles, les liens non autorisés ou les formulations à risque.",
        "question_too_short": "Veuillez fournir une question plus longue.",
        "footer_note": "Cette démo ne fournit pas de conseils financiers et ne prend aucune décision.",
        "audit_note": "Les journaux d’audit et de modération existent côté serveur et ne sont volontairement pas exposés dans l’interface utilisateur.",
        "lang_en": "Anglais",
        "lang_fr": "Français",
        "lang_es": "Espagnol",
        "pill_safe": "SÉCURITÉ D’ABORD",
        "pill_retrieval": "RECHERCHE UNIQUEMENT",
        "pill_demo": "DÉMO",
        "latest_cards": "Dernières cartes",
        "no_cards_yet": "Aucune carte pour le moment.",
        "safety_title": "Sécurité & Conformité (Garde-fous de la démo)",
        "safety_points": "Pas de conseils • Pas de décisions • Recherche uniquement • Contrôles PII • Liste blanche de domaines • Journaux/audit",
        "banned_kw": "Mots interdits",
        "allowed_domains": "Domaines autorisés (liens dans les cartes)",
        "min_score": "Score minimal de structure",
        "seed_note": "Si la base est vide, l’application charge automatiquement quelques cartes financières d’exemple.",
        "cards_title": "Toutes les cartes d’expérience",
        "cards_subtitle": "Pour la revue de démo. En production, des contrôles d’accès s’appliqueraient.",
        "sponsor_badge": "SPONSOR",
        "sponsor_top": "Espace partenaire (démo, sans suivi).",
        "sponsor_card": "Emplacement sponsorisé (démo, sans suivi).",
    },
    "es": {
        "app_title": "Tarjetas de Experiencia",
        "app_title_demo": "Demo de Tarjetas de Experiencia",
        "subtitle": "Soporte explicable y seguro para banca digital (solo recuperación)",
        "region_label": "Región",
        "region_ca": "Canadá",
        "region_us": "Estados Unidos",
        "language_label": "Idioma",
        "ask_title": "Haz una pregunta",
        "ask_hint": "Describe tu problema de banca digital (sin datos personales).",
        "ask_placeholder": "Ejemplo: Mi transferencia está pendiente / No puedo iniciar sesión / Recibí un mensaje sospechoso...",
        "ask_button": "Enviar",
        "results_title": "Tarjetas de Experiencia coincidentes",
        "no_results": "No se encontraron tarjetas relevantes para esta pregunta.",
        "why_this_match": "Por qué coincide",
        "score": "Puntuación",
        "category": "Categoría",
        "tags": "Etiquetas",
        "admin_link": "Admin",
        "cards_link": "Ver tarjetas",
        "admin_title": "Admin – Añadir Tarjeta de Experiencia",
        "admin_subtitle": "Añade solo experiencias financieras. Se aplican controles de seguridad.",
        "field_title": "Título",
        "field_category": "Categoría",
        "field_tags": "Etiquetas (separadas por comas, se recomiendan etiquetas en inglés)",
        "field_language": "Idioma del contenido",
        "field_content": "Contenido de la experiencia",
        "save_button": "Guardar",
        "back_home": "Volver al inicio",
        "presentation_on": "Modo presentación ACTIVADO",
        "presentation_tip": "Consejo: usa preguntas concisas y muestra la explicabilidad.",
        "error_prefix": "Error",
        "guardrail_rejected": "Envío rechazado por controles de seguridad.",
        "guardrail_hint": "Elimina datos personales, enlaces no permitidos o lenguaje riesgoso.",
        "question_too_short": "Por favor escribe una pregunta más larga.",
        "footer_note": "Esta demo no proporciona asesoramiento financiero y no toma decisiones.",
        "audit_note": "Los registros de auditoría y moderación existen en el servidor y no se muestran intencionalmente en la interfaz de usuario.",
        "lang_en": "Inglés",
        "lang_fr": "Francés",
        "lang_es": "Español",
        "pill_safe": "SEGURIDAD",
        "pill_retrieval": "SOLO RECUPERACIÓN",
        "pill_demo": "DEMO",
        "latest_cards": "Últimas tarjetas",
        "no_cards_yet": "Aún no hay tarjetas.",
        "safety_title": "Seguridad & Cumplimiento (Guardrails de la demo)",
        "safety_points": "Sin asesoría • Sin decisiones • Solo recuperación • Chequeos PII • Lista permitida de dominios • Logs/auditoría",
        "banned_kw": "Palabras prohibidas",
        "allowed_domains": "Dominios permitidos (links dentro de tarjetas)",
        "min_score": "Puntaje mínimo de estructura",
        "seed_note": "Si la base está vacía, la app carga automáticamente algunas tarjetas financieras de ejemplo.",
        "cards_title": "Todas las tarjetas de experiencia",
        "cards_subtitle": "Para revisión de demo. En producción habría control de acceso.",
        "sponsor_badge": "PATROCINADO",
        "sponsor_top": "Espacio de socio (demo, sin seguimiento).",
        "sponsor_card": "Espacio patrocinado (demo, sin seguimiento).",
    },
}

REGION_LANGS = {"ca": ["en", "fr"], "us": ["en", "es"]}

def t(lang: str, key: str) -> str:
    if lang not in I18N:
        lang = "en"
    return I18N[lang].get(key, I18N["en"].get(key, key))

# ----------------------------
# DB helpers + migrations
# ----------------------------
def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    conn = db()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS experiences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            tags TEXT NOT NULL,
            content TEXT NOT NULL,
            content_lang TEXT NOT NULL DEFAULT 'en',
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()

    # Migrations for older DBs
    cur.execute("PRAGMA table_info(experiences)")
    cols = [row[1] for row in cur.fetchall()]

    if "content_lang" not in cols:
        log.info("DB migration: adding column content_lang")
        cur.execute("ALTER TABLE experiences ADD COLUMN content_lang TEXT NOT NULL DEFAULT 'en'")
        conn.commit()

    if "created_at" not in cols:
        log.info("DB migration: adding column created_at")
        cur.execute("ALTER TABLE experiences ADD COLUMN created_at TEXT NOT NULL DEFAULT ''")
        conn.commit()

    conn.close()

init_db()

# ----------------------------
# Safety utilities
# ----------------------------
URL_RE = re.compile(r"(https?://[^\s]+)", re.IGNORECASE)

def normalize(text: str) -> str:
    text = (text or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text

def tokenize(text: str) -> List[str]:
    text = normalize(text).lower()
    tokens = re.split(r"[^a-z0-9]+", text)
    return [tok for tok in tokens if len(tok) >= 2]

def structure_score(content: str) -> int:
    c = normalize(content)
    score = 0
    if len(c) >= 120:
        score += 1
    if re.search(r"\b(i|we)\b.*\b(was|were|had|noticed|experienced)\b", c, re.IGNORECASE):
        score += 1
    if re.search(r"\b(i|we)\b.*\b(tried|did|checked|called|waited|updated|reset)\b", c, re.IGNORECASE):
        score += 1
    if re.search(r"\b(resolved|fixed|worked|failed|eventually|later|outcome|result)\b", c, re.IGNORECASE):
        score += 1
    if len(re.split(r"[.!?]+", c)) >= 3:
        score += 1
    return score

def contains_banned_keywords(text: str) -> bool:
    low = normalize(text).lower()
    return any(kw.lower() in low for kw in BANNED_KEYWORDS)

def extract_urls(text: str) -> List[str]:
    return URL_RE.findall(text or "")

def domain_allowed(url: str) -> bool:
    m = re.match(r"https?://([^/]+)", url.strip(), re.IGNORECASE)
    if not m:
        return False
    host = m.group(1).lower().split(":")[0]
    return any(host == d or host.endswith("." + d) for d in ALLOWED_DOMAINS)

def safety_check_experience(title: str, category: str, tags: str, content: str) -> Tuple[bool, str]:
    blob = " ".join([title or "", category or "", tags or "", content or ""])
    if contains_banned_keywords(blob):
        return False, "banned_keywords"
    for u in extract_urls(content):
        if not domain_allowed(u):
            return False, "disallowed_domain"
    if structure_score(content) < MIN_EXPERIENCE_STRUCTURE_SCORE:
        return False, "low_structure_score"
    return True, "ok"

def safety_check_question(question: str) -> Tuple[bool, str]:
    if contains_banned_keywords(question):
        return False, "banned_keywords"
    if extract_urls(question):
        return False, "url_not_allowed"
    if re.search(r"\b\d{11}\b", question):
        return False, "possible_id_number"
    if re.search(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", question):
        return False, "possible_phone"
    if re.search(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", question, re.IGNORECASE):
        return False, "possible_email"
    return True, "ok"

# ----------------------------
# Matching (simple, explainable)
# ----------------------------
def cosine_sim(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    dot = 0.0
    for k, av in a.items():
        dot += av * b.get(k, 0)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)

def score_experience(question: str, exp: sqlite3.Row) -> Dict[str, Any]:
    q_tokens = tokenize(question)
    q_counts = Counter(q_tokens)

    content = exp["content"] or ""
    c_tokens = tokenize(content)
    c_counts = Counter(c_tokens)

    sim = cosine_sim(q_counts, c_counts)  # 0..1
    score = sim * 100.0

    why = [f"text_similarity={sim:.2f}"]

    exp_tags = [x.strip().lower() for x in (exp["tags"] or "").split(",") if x.strip()]
    q_set = set(q_tokens)
    overlap = [tg for tg in exp_tags if tg in q_set]
    if overlap:
        bonus = min(15.0, 3.0 * len(overlap))
        score += bonus
        why.append(f"tag_overlap(+{bonus:.0f})={', '.join(overlap[:6])}")

    cat = (exp["category"] or "").lower()
    if cat and cat in normalize(question).lower():
        score += 5.0
        why.append("category_match(+5)")

    return {
        "id": exp["id"],
        "title": exp["title"],
        "category": exp["category"],
        "tags": exp["tags"],
        "content": exp["content"],
        "content_lang": exp["content_lang"] if "content_lang" in exp.keys() else "en",
        "created_at": exp["created_at"] if "created_at" in exp.keys() else "",
        "score": round(score, 2),
        "why": why,
    }

def get_top_matches(question: str, limit: int = 5) -> List[Dict[str, Any]]:
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM experiences ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()

    scored = [score_experience(question, r) for r in rows]
    scored = [s for s in scored if s["score"] >= 12.0]  # keep relevance tight
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:limit]

# ----------------------------
# Seed demo cards (only if DB empty)
# ----------------------------
def seed_if_empty() -> None:
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as c FROM experiences")
    count = int(cur.fetchone()["c"])
    if count > 0:
        conn.close()
        return

    now = datetime.utcnow().isoformat()
    seed_cards = [
        (
            "Transfer pending for a long time",
            "Transfers",
            "transfer,pending,processing,etransfer",
            "I initiated a transfer and it stayed pending longer than expected. I first checked the transaction history and the recipient details. Then I waited for the bank’s stated processing window and avoided retrying multiple times. The status eventually updated, and I kept the reference number in case I needed support later.",
            "en",
            now,
        ),
        (
            "Cannot log in after password reset",
            "Login",
            "login,password,reset,locked",
            "I tried to reset my password but still could not log in. I confirmed the new password worked on the website and then updated the mobile app. I also checked whether the account was temporarily locked after repeated attempts. After some time, login worked again and I enabled additional security checks.",
            "en",
            now,
        ),
        (
            "Suspicious message asking for OTP",
            "Fraud/Scam",
            "otp,scam,suspicious,phishing",
            "I received a message claiming to be from my bank asking for a one-time passcode. I did not share any codes and did not click links. I verified through the official website/app and used the bank’s official contact channel. The message was confirmed as phishing and I reported it.",
            "en",
            now,
        ),
        (
            "Card declined at ATM",
            "Cards/ATM",
            "card,atm,declined,limit",
            "My card was declined at an ATM. I checked daily limits and whether the card was temporarily blocked for security. I tried a different ATM and confirmed the card status in the app. The issue was related to limits, and it worked after adjusting settings through official channels.",
            "en",
            now,
        ),
    ]

    cur.executemany(
        "INSERT INTO experiences (title, category, tags, content, content_lang, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        seed_cards,
    )
    conn.commit()
    conn.close()
    log.info("Seeded %d sample cards (DB was empty).", len(seed_cards))

seed_if_empty()

# ----------------------------
# HTML helpers
# ----------------------------
def build_lang_switch(region: str, lang: str, presentation: str) -> str:
    allowed = REGION_LANGS.get(region, ["en"])
    pills = []
    for l in allowed:
        label = t(lang, f"lang_{l}")
        href = f"/?region={region}&lang={l}&presentation={presentation}"
        active = "active" if l == lang else ""
        pills.append(f'<a class="lang {active}" href="{href}">{label}</a>')
    return "\n".join(pills)

def safety_panel(lang: str) -> str:
    banned_preview = ", ".join(BANNED_KEYWORDS[:8]) + ("…" if len(BANNED_KEYWORDS) > 8 else "")
    domains_preview = ", ".join(ALLOWED_DOMAINS)
    return f"""
      <div class="panel">
        <h2 style="margin:0 0 6px;">{t(lang, "safety_title")}</h2>
        <div class="meta">{t(lang, "safety_points")}</div>
        <div style="height:10px;"></div>
        <div class="small"><strong>{t(lang, "banned_kw")}:</strong> {banned_preview}</div>
        <div class="small"><strong>{t(lang, "allowed_domains")}:</strong> {domains_preview}</div>
        <div class="small"><strong>{t(lang, "min_score")}:</strong> {MIN_EXPERIENCE_STRUCTURE_SCORE}</div>
        <div class="small" style="margin-top:8px;color:#444;">{t(lang, "seed_note")}</div>
      </div>
    """

def latest_cards_panel(region: str, lang: str, presentation: str) -> str:
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM experiences ORDER BY id DESC LIMIT 6")
    rows = cur.fetchall()
    conn.close()

    if not rows:
        body = f"<div class='small'>{t(lang, 'no_cards_yet')}</div>"
    else:
        cards = ""
        for r in rows:
            cards += f"""
              <div class="card">
                <h3>{r["title"]}</h3>
                <div class="small"><strong>{t(lang,"category")}:</strong> {r["category"]}</div>
                <div class="small"><strong>{t(lang,"tags")}:</strong> {r["tags"]}</div>
                <div style="height:8px;"></div>
                <div>{r["content"]}</div>
              </div>
            """
        body = f"<div class='cards'>{cards}</div>"

    return f"""
      <div class="panel">
        <div class="row" style="align-items:flex-end;">
          <h2 style="margin:0;">{t(lang, "latest_cards")}</h2>
          <div class="meta"><a class="link" href="/cards?region={region}&lang={lang}&presentation={presentation}">{t(lang, "cards_link")}</a></div>
        </div>
        <div style="height:10px;"></div>
        {body}
      </div>
    """

def page_html(region: str, lang: str, presentation: str) -> str:
    if region not in ("ca", "us"):
        region = "ca"
    allowed_langs = REGION_LANGS.get(region, ["en"])
    if lang not in allowed_langs:
        lang = "en"
    pres_on = (presentation == "1")

    # Title switches between product vs demo
    title_text = t(lang, "app_title_demo") if pres_on else t(lang, "app_title")

    pills = f"""
      <span class="pill">{t(lang, "pill_safe")}</span>
      <span class="pill">{t(lang, "pill_retrieval")}</span>
    """
    if pres_on:
        pills += f"""<span class="pill">{t(lang, "pill_demo")}</span>"""

    pres_banner = ""
    if pres_on:
        pres_banner = f"""
        <div class="banner">
          <strong>{t(lang, "presentation_on")}</strong><br/>
          <span>{t(lang, "presentation_tip")}</span>
        </div>
        """

    audit_note_html = ""
    if pres_on:
        audit_note_html = f"""
        <div class="footer" style="margin-top:12px; font-size:11px; color:#666;">
          {t(lang, "audit_note")}
        </div>
        """

    region_label = t(lang, "region_ca") if region == "ca" else t(lang, "region_us")

    return f"""
<!doctype html>
<html lang="{lang}">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title_text}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 0; background: #fafafa; color: #111; }}
    .wrap {{ max-width: 980px; margin: 0 auto; padding: 24px; }}
    .top {{ display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }}
    .title h1 {{ margin: 0; font-size: 28px; }}
    .title p {{ margin: 6px 0 0; color: #444; }}
    .pills {{ margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap; }}
    .pill {{ display: inline-block; padding: 6px 10px; border: 1px solid #ddd; border-radius: 999px; background: #fff; font-size: 12px; color: #333; }}
    .panel {{ background: #fff; border: 1px solid #e5e5e5; border-radius: 14px; padding: 18px; margin-top: 16px; }}
    label {{ display: block; font-weight: 700; margin-bottom: 6px; }}
    textarea {{ width: 100%; min-height: 110px; padding: 10px; border-radius: 10px; border: 1px solid #d7d7d7; font-size: 14px; }}
    button {{ padding: 10px 14px; border: none; border-radius: 10px; cursor: pointer; font-weight: 700; }}
    button.primary {{ background: #111; color: #fff; }}
    .row {{ display: flex; gap: 12px; flex-wrap: wrap; align-items: center; justify-content: space-between; }}
    .meta {{ color: #444; font-size: 13px; }}
    .langs {{ display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }}
    .lang {{ text-decoration: none; border: 1px solid #ddd; padding: 7px 10px; border-radius: 999px; background: #fff; color: #111; font-size: 13px; }}
    .lang.active {{ border-color: #111; }}
    .banner {{ background: #111; color: #fff; padding: 12px 14px; border-radius: 12px; margin-top: 14px; }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; margin-top: 12px; }}
    .card {{ background: #fff; border: 1px solid #e5e5e5; border-radius: 14px; padding: 14px; }}
    .card h3 {{ margin: 0 0 6px; font-size: 16px; }}
    .small {{ font-size: 12px; color: #555; }}
    .why {{ margin-top: 8px; font-size: 12px; color: #333; background: #f5f5f5; padding: 8px; border-radius: 10px; }}
    .err {{ color: #b00020; font-weight: 700; margin-top: 10px; }}
    .footer {{ margin-top: 22px; color: #555; font-size: 12px; }}
    a.link {{ color: #111; }}

    /* --- Sponsor/Ad placeholders (demo-only) --- */
    .ad-top {{
      position: sticky;
      top: 0;
      z-index: 50;
      background: #fff;
      border: 1px solid #e5e5e5;
      border-radius: 14px;
      padding: 10px 14px;
      margin-bottom: 14px;
    }}
    .ad-badge {{
      display:inline-block;
      font-size: 11px;
      padding: 2px 8px;
      border: 1px solid #ddd;
      border-radius: 999px;
      background: #fafafa;
      color:#333;
      margin-right: 8px;
      letter-spacing: .3px;
    }}
    .ad-text {{ font-size: 13px; color:#333; }}
    .ad-small {{ font-size: 11px; color:#666; margin-top:4px; }}
    .ad-card {{
      border-style: dashed;
      background: #fcfcfc;
    }}
  </style>
</head>
<body>
  <div class="wrap">

    <!-- Top sponsor/advertising placeholder (no tracking, demo-only) -->
    <div class="ad-top" id="adTop">
      <span class="ad-badge">{t(lang, "sponsor_badge")}</span>
      <span class="ad-text">{t(lang, "sponsor_top")}</span>
      <div class="ad-small">Demo-only placeholder — no tracking pixels, no third-party scripts.</div>
    </div>

    <div class="top">
      <div class="title">
        <h1>{title_text}</h1>
        <p>{t(lang, "subtitle")}</p>
        <div class="pills">{pills}</div>
      </div>
      <div class="panel" style="margin-top:0;">
        <div class="meta"><strong>{t(lang, "region_label")}:</strong> {region_label}</div>
        <div style="height:8px;"></div>
        <div class="meta"><strong>{t(lang, "language_label")}:</strong></div>
        <div class="langs">
          {build_lang_switch(region, lang, presentation)}
        </div>
        <div style="height:10px;"></div>
        <div class="meta">
          <a class="link" href="/admin?region={region}&lang={lang}&presentation={presentation}">{t(lang, "admin_link")}</a>
          &nbsp;•&nbsp;
          <a class="link" href="/cards?region={region}&lang={lang}&presentation={presentation}">{t(lang, "cards_link")}</a>
        </div>
      </div>
    </div>

    {pres_banner}

    {safety_panel(lang)}

    {latest_cards_panel(region, lang, presentation)}

    <div class="panel" id="askPanel">
      <h2 style="margin:0 0 6px;">{t(lang, "ask_title")}</h2>
      <div class="meta">{t(lang, "ask_hint")}</div>
      <div style="height:10px;"></div>
      <label for="q">{t(lang, "ask_title")}</label>
      <textarea id="q" placeholder="{t(lang, "ask_placeholder")}"></textarea>
      <div style="height:12px;"></div>
      <div class="row">
        <button class="primary" onclick="ask()">{t(lang, "ask_button")}</button>
        <div class="meta" id="status"></div>
      </div>
      <div class="err" id="err"></div>
    </div>

    <div class="panel" id="resultsPanel">
      <h2 style="margin:0;">{t(lang, "results_title")}</h2>
      <div class="cards" id="cards"></div>
      <div class="meta" id="empty" style="margin-top:10px;"></div>
    </div>

    {audit_note_html}

    <div class="footer">
      {t(lang, "footer_note")}
    </div>
  </div>

<script>
  async function ask() {{
    const q = document.getElementById("q").value;
    document.getElementById("err").textContent = "";
    document.getElementById("status").textContent = "…";
    document.getElementById("cards").innerHTML = "";
    document.getElementById("empty").textContent = "";

    const res = await fetch("/ask", {{
      method: "POST",
      headers: {{ "Content-Type": "application/json" }},
      body: JSON.stringify({{
        question: q,
        region: "{region}",
        lang: "{lang}"
      }})
    }});

    const data = await res.json();
    document.getElementById("status").textContent = "";

    if (!res.ok) {{
      document.getElementById("err").textContent = "{t(lang, "error_prefix")}: " + (data.detail || "Unknown error");
      const rp = document.getElementById("resultsPanel");
      if (rp) rp.scrollIntoView({{ behavior: "smooth", block: "start" }});
      return;
    }}

    // Insert sponsor/placeholder card at top of results
    const sponsorTop = document.createElement("div");
    sponsorTop.className = "card ad-card";
    sponsorTop.innerHTML = `
      <div class="small"><strong>{t(lang, "sponsor_badge")}</strong> (placeholder)</div>
      <div style="height:6px;"></div>
      <div>{t(lang, "sponsor_card")}</div>
    `;
    document.getElementById("cards").appendChild(sponsorTop);

    if (!data.matches || data.matches.length === 0) {{
      document.getElementById("empty").textContent = "{t(lang, "no_results")}";
      const rp = document.getElementById("resultsPanel");
      if (rp) rp.scrollIntoView({{ behavior: "smooth", block: "start" }});
      return;
    }}

    let idx = 0;
    for (const m of data.matches) {{
      // Optional: add another sponsor slot after 3rd item
      if (idx === 3) {{
        const sponsorMid = document.createElement("div");
        sponsorMid.className = "card ad-card";
        sponsorMid.innerHTML = `
          <div class="small"><strong>{t(lang, "sponsor_badge")}</strong> (placeholder)</div>
          <div style="height:6px;"></div>
          <div>{t(lang, "sponsor_card")}</div>
        `;
        document.getElementById("cards").appendChild(sponsorMid);
      }}

      const div = document.createElement("div");
      div.className = "card";
      div.innerHTML = `
        <h3>${{escapeHtml(m.title)}}</h3>
        <div class="small"><strong>{t(lang, "score")}:</strong> ${{m.score}}</div>
        <div class="small"><strong>{t(lang, "category")}:</strong> ${{escapeHtml(m.category)}}</div>
        <div class="small"><strong>{t(lang, "tags")}:</strong> ${{escapeHtml(m.tags)}}</div>
        <div style="height:8px;"></div>
        <div>${{escapeHtml(m.content)}}</div>
        <div class="why"><strong>{t(lang, "why_this_match")}:</strong><br/>${{escapeHtml(m.why.join(" · "))}}</div>
      `;
      document.getElementById("cards").appendChild(div);
      idx++;
    }}

    // After rendering results, scroll to results panel
    const rp = document.getElementById("resultsPanel");
    if (rp) rp.scrollIntoView({{ behavior: "smooth", block: "start" }});
  }}

  function escapeHtml(str) {{
    return (str || "").replace(/[&<>"']/g, function(m) {{
      return ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}})[m];
    }});
  }}
</script>

</body>
</html>
"""

# ----------------------------
# Routes
# ----------------------------
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    region = request.query_params.get("region", "ca").lower()
    lang = request.query_params.get("lang", "en").lower()
    presentation = request.query_params.get("presentation", "0")
    return HTMLResponse(page_html(region, lang, presentation))

@app.get("/cards", response_class=HTMLResponse)
def cards(request: Request):
    region = request.query_params.get("region", "ca").lower()
    lang = request.query_params.get("lang", "en").lower()
    presentation = request.query_params.get("presentation", "0")

    if region not in ("ca", "us"):
        region = "ca"
    if lang not in REGION_LANGS.get(region, ["en"]):
        lang = "en"

    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM experiences ORDER BY id DESC LIMIT 200")
    rows = cur.fetchall()
    conn.close()

    items = ""
    for r in rows:
        cl = r["content_lang"] if "content_lang" in r.keys() else "en"
        items += f"""
        <div class="card">
          <h3>{r["title"]}</h3>
          <div class="small"><strong>{t(lang,"category")}:</strong> {r["category"]}</div>
          <div class="small"><strong>{t(lang,"tags")}:</strong> {r["tags"]}</div>
          <div class="small"><strong>Lang:</strong> {cl}</div>
          <div style="height:8px;"></div>
          <div>{r["content"]}</div>
        </div>
        """

    html = f"""
<!doctype html>
<html lang="{lang}">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{t(lang,"cards_title")}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 0; background: #fafafa; color: #111; }}
    .wrap {{ max-width: 980px; margin: 0 auto; padding: 24px; }}
    .panel {{ background: #fff; border: 1px solid #e5e5e5; border-radius: 14px; padding: 18px; margin-top: 16px; }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; margin-top: 12px; }}
    .card {{ background: #fff; border: 1px solid #e5e5e5; border-radius: 14px; padding: 14px; }}
    .card h3 {{ margin: 0 0 6px; font-size: 16px; }}
    .small {{ font-size: 12px; color: #555; }}
    a.link {{ color: #111; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="panel" style="margin-top:0;">
      <h1 style="margin:0;">{t(lang,"cards_title")}</h1>
      <p style="margin:6px 0 0;color:#444;">{t(lang,"cards_subtitle")}</p>
      <p style="margin:10px 0 0;">
        <a class="link" href="/?region={region}&lang={lang}&presentation={presentation}">{t(lang,"back_home")}</a>
        &nbsp;•&nbsp;
        <a class="link" href="/admin?region={region}&lang={lang}&presentation={presentation}">{t(lang,"admin_link")}</a>
      </p>
    </div>
    <div class="panel">
      <div class="cards">
        {items if items else "<div class='small'>No cards.</div>"}
      </div>
    </div>
  </div>
</body>
</html>
"""
    return HTMLResponse(html)

@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request):
    region = request.query_params.get("region", "ca").lower()
    lang = request.query_params.get("lang", "en").lower()
    presentation = request.query_params.get("presentation", "0")

    if region not in ("ca", "us"):
        region = "ca"
    if lang not in REGION_LANGS.get(region, ["en"]):
        lang = "en"

    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM experiences ORDER BY id DESC LIMIT 30")
    rows = cur.fetchall()
    conn.close()

    options = []
    for l in ["en", "fr", "es"]:
        options.append(f'<option value="{l}">{t(lang, "lang_"+l)}</option>')
    options_html = "\n".join(options)

    items = ""
    for r in rows:
        cl = r["content_lang"] if "content_lang" in r.keys() else "en"
        items += f"""
        <div class="card">
          <h3>{r["title"]}</h3>
          <div class="small"><strong>{t(lang, "category")}:</strong> {r["category"]}</div>
          <div class="small"><strong>{t(lang, "tags")}:</strong> {r["tags"]}</div>
          <div class="small"><strong>Lang:</strong> {cl}</div>
          <div style="height:8px;"></div>
          <div>{r["content"]}</div>
        </div>
        """

    html = f"""
<!doctype html>
<html lang="{lang}">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{t(lang, "admin_title")}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 0; background: #fafafa; color: #111; }}
    .wrap {{ max-width: 980px; margin: 0 auto; padding: 24px; }}
    .panel {{ background: #fff; border: 1px solid #e5e5e5; border-radius: 14px; padding: 18px; margin-top: 16px; }}
    label {{ display: block; font-weight: 700; margin: 12px 0 6px; }}
    input, textarea, select {{ width: 100%; padding: 10px; border-radius: 10px; border: 1px solid #d7d7d7; font-size: 14px; }}
    textarea {{ min-height: 140px; }}
    button {{ padding: 10px 14px; border: none; border-radius: 10px; cursor: pointer; font-weight: 700; background: #111; color: #fff; margin-top: 12px; }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; margin-top: 12px; }}
    .card {{ background: #fff; border: 1px solid #e5e5e5; border-radius: 14px; padding: 14px; }}
    .card h3 {{ margin: 0 0 6px; font-size: 16px; }}
    .small {{ font-size: 12px; color: #555; }}
    a.link {{ color: #111; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="panel" style="margin-top:0;">
      <h1 style="margin:0;">{t(lang, "admin_title")}</h1>
      <p style="margin:6px 0 0;color:#444;">{t(lang, "admin_subtitle")}</p>
      <p style="margin:10px 0 0;">
        <a class="link" href="/?region={region}&lang={lang}&presentation={presentation}">{t(lang, "back_home")}</a>
        &nbsp;•&nbsp;
        <a class="link" href="/cards?region={region}&lang={lang}&presentation={presentation}">{t(lang, "cards_link")}</a>
      </p>
    </div>

    <div class="panel">
      <form method="post" action="/admin/add?region={region}&lang={lang}&presentation={presentation}">
        <label>{t(lang, "field_title")}</label>
        <input name="title" required />

        <label>{t(lang, "field_category")}</label>
        <input name="category" required placeholder="e.g., Login, Transfers, Cards/ATM, Payments, Fraud/Scam" />

        <label>{t(lang, "field_tags")}</label>
        <input name="tags" required placeholder="e.g., otp, pending, transfer, login, suspicious" />

        <label>{t(lang, "field_language")}</label>
        <select name="content_lang">
          {options_html}
        </select>

        <label>{t(lang, "field_content")}</label>
        <textarea name="content" required></textarea>

        <button type="submit">{t(lang, "save_button")}</button>
      </form>
    </div>

    <div class="panel">
      <h2 style="margin:0 0 10px;">{t(lang, "latest_cards")}</h2>
      <div class="cards">
        {items if items else f"<div class='small'>{t(lang, 'no_cards_yet')}</div>"}
      </div>
    </div>
  </div>
</body>
</html>
"""
    return HTMLResponse(html)

@app.post("/admin/add")
def admin_add(
    request: Request,
    title: str = Form(...),
    category: str = Form(...),
    tags: str = Form(...),
    content: str = Form(...),
    content_lang: str = Form("en"),
):
    region = request.query_params.get("region", "ca").lower()
    lang = request.query_params.get("lang", "en").lower()
    presentation = request.query_params.get("presentation", "0")

    title = normalize(title)
    category = normalize(category)
    tags = normalize(tags)
    content = normalize(content)
    content_lang = (content_lang or "en").lower()
    if content_lang not in ("en", "fr", "es"):
        content_lang = "en"

    ok, reason = safety_check_experience(title, category, tags, content)
    log.info("ADMIN_ADD safety=%s reason=%s title=%s", ok, reason, title)

    if not ok:
        raise HTTPException(status_code=400, detail=f"{t(lang, 'guardrail_rejected')} ({reason})")

    created_at = datetime.utcnow().isoformat()

    conn = db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO experiences (title, category, tags, content, content_lang, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (title, category, tags, content, content_lang, created_at),
    )
    conn.commit()
    conn.close()

    return RedirectResponse(url=f"/admin?region={region}&lang={lang}&presentation={presentation}", status_code=303)

@app.post("/ask")
def ask(payload: Dict[str, Any]):
    question = normalize(payload.get("question", ""))
    region = (payload.get("region", "ca") or "ca").lower()
    lang = (payload.get("lang", "en") or "en").lower()

    if region not in ("ca", "us"):
        region = "ca"
    if lang not in REGION_LANGS.get(region, ["en"]):
        lang = "en"

    if not question or len(question) < 8:
        raise HTTPException(status_code=400, detail=t(lang, "question_too_short"))

    ok, reason = safety_check_question(question)
    log.info("ASK safety=%s reason=%s q=%s", ok, reason, question[:180])

    if not ok:
        detail = f"{t(lang, 'guardrail_rejected')} ({reason}). {t(lang, 'guardrail_hint')}"
        raise HTTPException(status_code=400, detail=detail)

    matches = get_top_matches(question, limit=5)
    return JSONResponse({"question": question, "matches": matches})
