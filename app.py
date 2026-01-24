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
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("experience-cards")

# ----------------------------
# App
# ----------------------------
app = FastAPI(title="Experience Cards", version="1.8.0")

# Two separate DBs to GUARANTEE demo-only cards don't get mixed with live data.
APP_DB_PATH = "app.db"          # normal program data (your added cards)
DEMO_DB_PATH = "demo_only.db"   # presentation/demo data (curated seed only)

# ----------------------------
# Demo matching behavior (B: professional)
# ----------------------------
MIN_MATCH_SCORE = 18.0     # raise threshold to reduce "keyword spam" feel
MAX_MATCHES = 5            # compute up to 5 matches (Top-3 shown, rest via "Show more")
TOP_VISIBLE = 3            # show top 3 by default

# ----------------------------
# Guardrails (config)
# ----------------------------
BANNED_KEYWORDS = [
    "kill", "suicide", "bomb", "terror", "nazi",
    "send me your otp", "share your otp", "give me your password", "bank password",
    "one-time passcode", "otp code",
    "nudes", "sex",
]

ALLOWED_DOMAINS = [
    "canada.ca",
    "fcac-acfc.gc.ca",
    "cba.ca",
    "consumerfinance.gov",
    "ftc.gov",
    "usa.gov",
    "fca.org.uk",
]

MIN_EXPERIENCE_STRUCTURE_SCORE = 4

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
        "fallback_note": "Note: This demo answer is based on a limited set of curated experience cards. In production, coverage expands as new experiences are added.",
        "why_this_match": "Why this match",
        "score": "Score",
        "category": "Category",
        "tags": "Tags",

        # B behavior labels
        "confidence": "Confidence",
        "high_conf": "High",
        "med_conf": "Medium",
        "low_conf": "Low",
        "low_ref": "Low (reference)",
        "show_more": "Show more matches",

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
        "seed_note": "In presentation mode, the demo uses a separate database that contains only curated cards (15 per region).",
        "cards_title": "All Experience Cards",
        "cards_subtitle": "For review. In production, access controls would apply.",
        "english_only_note": "For this demo, matching works in English (curated English cards). The UI can be viewed in your selected language.",
        "examples_title": "Example questions (English)",
        "copy_hint": "Tip: click an example to copy it into the input box.",
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
        "fallback_note": "Note : cette démo répond à partir d’un ensemble limité de cartes d’expérience sélectionnées. En production, la couverture s’étend au fur et à mesure que de nouvelles expériences sont ajoutées.",
        "why_this_match": "Pourquoi cette correspondance",
        "score": "Score",
        "category": "Catégorie",
        "tags": "Étiquettes",

        # B behavior labels
        "confidence": "Confiance",
        "high_conf": "Élevée",
        "med_conf": "Moyenne",
        "low_conf": "Faible",
        "low_ref": "Faible (référence)",
        "show_more": "Afficher plus de correspondances",

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
        "seed_note": "En mode présentation, la démo utilise une base séparée ne contenant que des cartes sélectionnées (15 par région).",
        "cards_title": "Toutes les cartes d’expérience",
        "cards_subtitle": "Pour revue. En production, des contrôles d’accès s’appliqueraient.",
        "english_only_note": "Pour cette démo, l’appariement fonctionne en anglais (cartes en anglais). L’interface peut être affichée dans la langue sélectionnée.",
        "examples_title": "Questions d’exemple (anglais)",
        "copy_hint": "Astuce : cliquez sur un exemple pour le copier dans la zone de saisie.",
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
        "fallback_note": "Nota: esta demo responde usando un conjunto limitado de tarjetas de experiencia seleccionadas. En producción, la cobertura crece a medida que se agregan nuevas experiencias.",
        "why_this_match": "Por qué coincide",
        "score": "Puntuación",
        "category": "Categoría",
        "tags": "Etiquetas",

        # B behavior labels
        "confidence": "Confianza",
        "high_conf": "Alta",
        "med_conf": "Media",
        "low_conf": "Baja",
        "low_ref": "Baja (referencia)",
        "show_more": "Mostrar más coincidencias",

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
        "allowed_domains": "Dominios permitidos (links dentro de las tarjetas)",
        "min_score": "Puntaje mínimo de estructura",
        "seed_note": "En modo presentación, la demo usa una base separada que contiene solo tarjetas seleccionadas (15 por región).",
        "cards_title": "Todas las tarjetas de experiencia",
        "cards_subtitle": "Para revisión. En producción habría control de acceso.",
        "english_only_note": "En esta demo, el emparejamiento funciona en inglés (tarjetas en inglés). La interfaz puede verse en el idioma seleccionado.",
        "examples_title": "Preguntas de ejemplo (inglés)",
        "copy_hint": "Consejo: haz clic en un ejemplo para copiarlo al cuadro de texto.",
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
def db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db_for(db_path: str) -> None:
    conn = db(db_path)
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

    cur.execute("PRAGMA table_info(experiences)")
    cols = [row[1] for row in cur.fetchall()]

    if "content_lang" not in cols:
        cur.execute("ALTER TABLE experiences ADD COLUMN content_lang TEXT NOT NULL DEFAULT 'en'")
        conn.commit()
    if "created_at" not in cols:
        cur.execute("ALTER TABLE experiences ADD COLUMN created_at TEXT NOT NULL DEFAULT ''")
        conn.commit()

    conn.close()


init_db_for(APP_DB_PATH)
init_db_for(DEMO_DB_PATH)

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

    c_tokens = tokenize(exp["content"] or "")
    c_counts = Counter(c_tokens)

    sim = cosine_sim(q_counts, c_counts)
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
        "content_lang": exp["content_lang"],
        "created_at": exp["created_at"],
        "score": round(score, 2),
        "why": why,
    }


def _region_clause(region: str) -> Tuple[str, Tuple[Any, ...]]:
    """
    Since we don't store a separate region column, we filter demo cards by tags.
    Seeded cards include 'canada' or 'usa' in tags.
    """
    if region == "us":
        return "(tags LIKE ?)", ("%usa%",)
    return "(tags LIKE ?)", ("%canada%",)


def get_top_matches(
    db_path: str,
    question: str,
    region: str,
    demo_region_filter: bool,
    limit: int = MAX_MATCHES
) -> List[Dict[str, Any]]:
    conn = db(db_path)
    cur = conn.cursor()

    if demo_region_filter:
        clause, params = _region_clause(region)
        cur.execute(f"SELECT * FROM experiences WHERE {clause} ORDER BY id DESC", params)
    else:
        cur.execute("SELECT * FROM experiences ORDER BY id DESC")

    rows = cur.fetchall()
    conn.close()

    scored = [score_experience(question, r) for r in rows]
    scored = [s for s in scored if s["score"] >= MIN_MATCH_SCORE]
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:limit]


# ----------------------------
# HTML helpers
# ----------------------------
def escape_html(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#039;")


def escape_js(s: str) -> str:
    return '"' + (s or "").replace("\\", "\\\\").replace('"', '\\"') + '"'


# ----------------------------
# Seed demo DB with ONLY curated cards (15 per region) - guaranteed
# ----------------------------
def ensure_demo_db_seeded_only() -> None:
    conn = db(DEMO_DB_PATH)
    cur = conn.cursor()

    # Hard guarantee: demo DB contains ONLY curated set
    cur.execute("DELETE FROM experiences")
    conn.commit()

    now = datetime.utcnow().isoformat()
    seed_cards: List[Tuple[str, str, str, str, str, str]] = []

    # Canada 15 (English content)
    seed_cards += [
        ("CA: Newcomer account opening at a branch", "Onboarding",
         "newcomer,account,documents,branch,canada",
         "When I first arrived in Canada, I wanted to open a bank account and was unsure about the required documents. I brought my passport and immigration papers to a branch and explained my situation. The staff clarified which newcomer options were available and which documents were acceptable at that stage. Requirements can vary by institution, so asking directly helped me move forward quickly.",
         "en", now),
        ("CA: Can I open an account without a SIN yet?", "Onboarding",
         "sin,identity,newcomer,requirements,canada",
         "I was confused about whether I needed a SIN to open a bank account. At the branch, I asked what was possible before my SIN was issued. The representative explained that some banks allow account opening without a SIN initially, sometimes with limitations. I was told I could update my profile later once my SIN became available.",
         "en", now),
        ("CA: No permanent address during onboarding", "Onboarding",
         "address,newcomer,temporary,documents,canada",
         "When opening an account, I did not have a permanent address yet. I explained that I was in temporary housing and provided a temporary address for initial setup. The bank accepted it and advised me to update the address later. That allowed me to get started without waiting for permanent housing.",
         "en", now),
        ("CA: Mobile banking first-time secure setup", "Digital Access",
         "mobile,security,2fa,password,canada",
         "When I started using mobile banking, I focused on secure setup. I enabled two-factor authentication, created a strong password, and installed the app only from the official store. I avoided public Wi-Fi for login and reviewed security settings in the app. These steps made me feel more confident using digital banking.",
         "en", now),
        ("CA: Forgot password and avoided lockout", "Digital Access",
         "password,login,reset,lockout,canada",
         "After forgetting my password, I used the official reset flow in the app. I followed identity verification steps carefully and avoided repeated attempts that could trigger a lockout. After the reset, I confirmed I could log in successfully and updated any saved credentials on my device.",
         "en", now),
        ("CA: App language barriers and safe coping strategies", "Digital Access",
         "language,accessibility,help,canada",
         "I struggled with English-only screens in a banking app. Instead of sharing passwords with others, I used built-in accessibility features and kept notes of key menu terms. When needed, I asked for guidance through official support channels. This helped me avoid risky shortcuts while still completing tasks.",
         "en", now),
        ("CA: Debit vs credit card as a newcomer", "Cards",
         "debit,credit,credit_history,newcomer,canada",
         "I was unsure whether to use debit or apply for a credit card. I learned that debit is useful for everyday spending, while a credit card can help build credit history if used responsibly. I started with simple spending limits, paid balances on time, and monitored transactions regularly.",
         "en", now),
        ("CA: Card declined due to limits or fraud protection", "Cards",
         "card,declined,limits,fraud_protection,canada",
         "My card was declined at a merchant, and I did not know why. I checked my daily limits and whether the bank had flagged the transaction for security. I verified the card status in the app and tried a smaller transaction later. The issue turned out to be a security hold, which cleared after confirmation through official channels.",
         "en", now),
        ("CA: Contactless tap payments safety basics", "Payments",
         "contactless,tap,limits,security,canada",
         "I wondered whether tap payments were safe. I learned that contactless has transaction limits and that I can review settings and monitor transactions in the app. I kept notifications enabled and reported anything suspicious quickly. This made contactless payments feel safer and more manageable.",
         "en", now),
        ("CA: CRA phone call scam recognition", "Fraud/Scam",
         "cra,scam,phone,phishing,canada",
         "I received a call claiming to be from the CRA and demanding immediate payment. I did not share any personal information and ended the call. I verified the situation using official government channels and confirmed it was a scam attempt. The key was to avoid reacting under pressure and to use only trusted contacts.",
         "en", now),
        ("CA: Email phishing pretending to be a bank", "Fraud/Scam",
         "phishing,email,link,security,canada",
         "I got an email that looked like it was from my bank and asked me to click a link. I did not click it. Instead, I opened my banking app directly and checked for alerts, then used official support contacts to confirm. This helped me avoid phishing and keep my account secure.",
         "en", now),
        ("CA: Account frozen after suspicious activity", "Fraud/Scam",
         "account,frozen,suspicious_activity,verification,canada",
         "My account access was restricted after unusual activity was detected. I followed the bank’s official verification steps and confirmed recent transactions. After identity checks, access was restored. I learned that quick verification through official channels is the safest way to resolve a freeze.",
         "en", now),
        ("CA: Interac e-Transfer delayed or pending", "Transfers",
         "interac,e-transfer,pending,delay,canada",
         "I sent an Interac e-Transfer and it did not arrive immediately. I checked the recipient details and whether the transfer was pending or on a security hold. I avoided sending duplicates and waited within the stated processing window. The transfer later completed, and I kept the reference details in case support was needed.",
         "en", now),
        ("CA: Overdraft confusion and avoiding fees", "Fees",
         "overdraft,fees,negative_balance,avoid,canada",
         "I noticed my balance went negative and I was unsure what overdraft meant. I reviewed my account terms and learned how overdraft fees may apply. I adjusted alerts, monitored upcoming payments, and kept a buffer to avoid future surprises. Understanding the rules helped me prevent repeated fees.",
         "en", now),
        ("CA: Unexpected monthly account fee", "Fees",
         "account_fee,monthly_fee,waiver,plan,canada",
         "I saw a monthly fee and did not expect it. I checked my account plan details and learned that fee waivers may depend on minimum balance or certain conditions. I compared account types and adjusted my plan to match my usage. This reduced unexpected charges going forward.",
         "en", now),
    ]

    # USA 15 (English content)
    seed_cards += [
        ("US: Opening a bank account (ID and proof basics)", "Onboarding",
         "account,opening,id,documents,usa",
         "When opening a bank account in the US, I was asked for identification and basic proof details. I prepared government-issued ID and confirmed what the bank accepted for verification. I learned requirements vary by institution, so checking the bank’s official guidance helped me avoid surprises during onboarding.",
         "en", now),
        ("US: No SSN yet – discussing options", "Onboarding",
         "ssn,itin,account,requirements,usa",
         "I did not have an SSN and was unsure if I could open an account. I asked the bank what alternatives were acceptable and learned some institutions may support different verification paths. I documented what the bank requested and followed official instructions to stay compliant with their process.",
         "en", now),
        ("US: Online vs branch onboarding differences", "Onboarding",
         "online,branch,verification,onboarding,usa",
         "I was deciding between opening an account online or at a branch. Online onboarding was faster but required strict identity verification steps. Branch onboarding allowed me to ask questions and clarify requirements in real time. I chose based on which path reduced confusion and improved confidence.",
         "en", now),
        ("US: Mobile app login issues and device trust", "Digital Access",
         "mobile,login,device,reset,usa",
         "I could not log in to my banking app after changing settings on my phone. I checked whether the device needed re-verification and used the app’s official recovery steps. I avoided repeated attempts that might lock the account. After verification, access returned and I enabled security notifications.",
         "en", now),
        ("US: Why 2FA matters and what to do if it fails", "Digital Access",
         "2fa,security,codes,access,usa",
         "I wondered why two-factor authentication was required. I learned it adds protection beyond a password. When a code did not arrive, I checked my contact settings and used official recovery steps. Keeping 2FA enabled reduced account takeover risk.",
         "en", now),
        ("US: Shared device risks for banking apps", "Digital Access",
         "shared_device,privacy,security,logout,usa",
         "My family shared a device and I worried about privacy in banking apps. I learned that shared devices increase risk. I avoided saving passwords, logged out after sessions, and used device-level protections. When possible, using a personal device reduced accidental exposure.",
         "en", now),
        ("US: Debit card declined at a merchant", "Cards",
         "debit,declined,limits,merchant,usa",
         "My debit card was declined unexpectedly. I checked whether I had reached a daily limit or whether the transaction was blocked for security. I reviewed account alerts and tried a smaller transaction. The issue was resolved after confirming activity through official channels.",
         "en", now),
        ("US: First credit card basics and responsible use", "Cards",
         "credit_card,basics,limit,pay_on_time,usa",
         "I wanted my first credit card but was worried about mistakes. I learned that paying on time and keeping utilization low helps avoid problems. I started with a small limit and used alerts to track spending. Responsible use helped me build confidence and avoid fees.",
         "en", now),
        ("US: Online purchases and fraud monitoring", "Payments",
         "online_payments,fraud,alerts,secure,usa",
         "I was unsure how safe online payments were. I enabled transaction alerts, used trusted merchants, and avoided saving payment details on unknown sites. When something looked suspicious, I checked official support guidance. Monitoring and quick reporting were key to staying safe.",
         "en", now),
        ("US: IRS scam call recognition", "Fraud/Scam",
         "irs,scam,phone,pressure,usa",
         "I received a call claiming to be from the IRS and demanding immediate action. I did not share personal data and ended the call. I verified through official government channels and learned that scam calls often use pressure tactics. Using trusted contacts prevented a costly mistake.",
         "en", now),
        ("US: Person-to-person transfer scams (P2P risk)", "Fraud/Scam",
         "p2p,transfer,scam,irreversible,usa",
         "I learned that some person-to-person transfers can be hard to reverse. I verify recipients carefully before sending money and I avoid urgency tactics. When in doubt, I follow official guidance and I do not send funds until verification is clear.",
         "en", now),
        ("US: Account locked after suspicious login", "Fraud/Scam",
         "account,locked,suspicious_login,reset,usa",
         "My account was locked after unusual login activity. I followed the official steps to verify identity and reset access. I reviewed recent activity and changed credentials using secure methods. After recovery, I enabled additional security protections to reduce repeat incidents.",
         "en", now),
        ("US: Overdraft fees and avoiding repeat charges", "Fees",
         "overdraft,fees,balance,alerts,usa",
         "I was surprised by an overdraft fee and wanted to avoid it in the future. I learned to monitor my balance, set alerts, and keep a small buffer. I reviewed which transactions were pending versus posted. These habits helped reduce unexpected fees.",
         "en", now),
        ("US: Understanding statements (pending vs posted)", "Statements",
         "statement,pending,posted,charges,usa",
         "I found bank statements confusing and did not know why totals changed. I learned the difference between pending and posted transactions and how holds can affect available balance. Reviewing statement categories helped me spot unfamiliar charges early and take action quickly if needed.",
         "en", now),
        ("US: Who to contact for support (branch vs hotline vs in-app)", "Support",
         "support,branch,hotline,in_app,usa",
         "I was unsure who to contact when something went wrong. I use official support paths: in-app help for basic issues, hotline for urgent access problems, and a branch visit when identity verification is required. Choosing the right channel reduces delays.",
         "en", now),
    ]

    cur.executemany(
        "INSERT INTO experiences (title, category, tags, content, content_lang, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        seed_cards,
    )
    conn.commit()
    conn.close()
    log.info("Demo DB reset & seeded with %d curated cards (15 CA + 15 US).", len(seed_cards))


# Seed demo DB on startup (always reset -> guarantee)
ensure_demo_db_seeded_only()


# ----------------------------
# UI helpers (region/language, panels)
# ----------------------------
REGION_LANGS = {"ca": ["en", "fr"], "us": ["en", "es"]}


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
        <div class="small"><strong>{t(lang, "banned_kw")}:</strong> {escape_html(banned_preview)}</div>
        <div class="small"><strong>{t(lang, "allowed_domains")}:</strong> {escape_html(domains_preview)}</div>
        <div class="small"><strong>{t(lang, "min_score")}:</strong> {MIN_EXPERIENCE_STRUCTURE_SCORE}</div>
        <div class="small" style="margin-top:8px;color:#444;">{t(lang, "seed_note")}</div>
      </div>
    """


def pick_db_path(presentation: str) -> str:
    return DEMO_DB_PATH if presentation == "1" else APP_DB_PATH


def region_label(lang: str, region: str) -> str:
    return t(lang, "region_ca") if region == "ca" else t(lang, "region_us")


def _region_clause(region: str) -> Tuple[str, Tuple[Any, ...]]:
    # (duplicated small helper for UI queries)
    if region == "us":
        return "(tags LIKE ?)", ("%usa%",)
    return "(tags LIKE ?)", ("%canada%",)


def latest_cards_panel(db_path: str, region: str, lang: str, presentation: str) -> str:
    conn = db(db_path)
    cur = conn.cursor()

    # In demo mode, show only cards for the chosen region to avoid confusion
    if presentation == "1":
        clause, params = _region_clause(region)
        cur.execute(f"SELECT * FROM experiences WHERE {clause} ORDER BY id DESC LIMIT 6", params)
    else:
        cur.execute("SELECT * FROM experiences ORDER BY id DESC LIMIT 6")

    rows = cur.fetchall()
    conn.close()

    if not rows:
        body = f"<div class='small'>{t(lang, 'no_cards_yet')}</div>"
    else:
        cards_html = ""
        for r in rows:
            cards_html += f"""
              <div class="card">
                <h3>{escape_html(r["title"])}</h3>
                <div class="small"><strong>{t(lang,"category")}:</strong> {escape_html(r["category"])}</div>
                <div class="small"><strong>{t(lang,"tags")}:</strong> {escape_html(r["tags"])}</div>
                <div style="height:8px;"></div>
                <div>{escape_html(r["content"])}</div>
              </div>
            """
        body = f"<div class='cards'>{cards_html}</div>"

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


# ----------------------------
# Example questions (EN only for demo matching)
# ----------------------------
def example_questions(region: str) -> List[str]:
    if region == "us":
        return [
            "My debit card was declined at a store—what should I check first?",
            "I can’t log in to the mobile banking app. What steps can I try safely?",
            "I received a call claiming to be from the IRS—how can I verify it?",
            "I was charged an overdraft fee—how can I avoid it next time?",
            "I don’t recognize a transaction on my statement—what should I do?",
            "I’m not sure who to contact: in-app support, hotline, or branch?",
        ]
    return [
        "I’m new to Canada—what documents do I need to open a bank account?",
        "I don’t have a SIN yet—can I still open an account?",
        "My Interac e-Transfer is pending—what should I check?",
        "I forgot my banking app password—how do I reset it safely?",
        "I got an email that looks like it’s from my bank—should I click the link?",
        "My card was declined—could it be a limit or a security hold?",
    ]


def examples_panel(region: str, lang: str) -> str:
    qs = example_questions(region)
    items = ""
    for q in qs:
        items += f'<button class="ex" type="button" onclick="useExample({escape_js(q)})">{escape_html(q)}</button>'
    return f"""
      <div class="panel">
        <div class="row" style="align-items:flex-end;">
          <h2 style="margin:0;">{t(lang, "examples_title")}</h2>
          <div class="meta">{t(lang, "copy_hint")}</div>
        </div>
        <div style="height:10px;"></div>
        <div class="examples">{items}</div>
      </div>
    """


# ----------------------------
# Confidence labels (B behavior)
# ----------------------------
def confidence_label(score: float) -> str:
    if score >= 30.0:
        return "high"
    if score >= 22.0:
        return "med"
    return "low"


def page_html(region: str, lang: str, presentation: str) -> str:
    if region not in ("ca", "us"):
        region = "ca"
    allowed_langs = REGION_LANGS.get(region, ["en"])
    if lang not in allowed_langs:
        lang = "en"

    pres_on = (presentation == "1")
    title_text = t(lang, "app_title_demo") if pres_on else t(lang, "app_title")

    pills = f"""
      <span class="pill">{t(lang, "pill_safe")}</span>
      <span class="pill">{t(lang, "pill_retrieval")}</span>
    """
    if pres_on:
        pills += f"""<span class="pill">{t(lang, "pill_demo")}</span>"""

    pres_banner = ""
    audit_note_html = ""
    english_note_html = ""
    if pres_on:
        pres_banner = f"""
        <div class="banner">
          <strong>{t(lang, "presentation_on")}</strong><br/>
          <span>{t(lang, "presentation_tip")}</span>
        </div>
        """
        audit_note_html = f"""
        <div class="footer" style="margin-top:12px; font-size:11px; color:#666;">
          {t(lang, "audit_note")}
        </div>
        """
        english_note_html = f"""
        <div class="meta" style="margin-top:8px; padding:10px 12px; border:1px solid #e5e5e5; border-radius:12px; background:#fff;">
          <strong>Note:</strong> {t(lang, "english_only_note")}
        </div>
        """

    # In presentation mode, avoid showing any admin link
    admin_link_html = ""
    if not pres_on:
        admin_link_html = f'<a class="link" href="/admin?region={region}&lang={lang}&presentation={presentation}">{t(lang, "admin_link")}</a>&nbsp;•&nbsp;'

    region_text_html = f"""
      <div class="meta"><strong>{t(lang, "region_label")}:</strong> {region_label(lang, region)}</div>
    """

    db_path = pick_db_path(presentation)

    return f"""
<!doctype html>
<html lang="{lang}">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape_html(title_text)}</title>
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
    button.secondary {{ background: #fff; color: #111; border: 1px solid #ddd; }}
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
    .examples {{ display:flex; flex-wrap:wrap; gap:10px; }}
    .ex {{ background:#fff; border:1px solid #ddd; color:#111; padding:10px 12px; border-radius:12px; font-weight:600; text-align:left; }}
    .ex:hover {{ border-color:#111; }}
    .badge {{ display:inline-block; padding:4px 8px; border-radius:999px; border:1px solid #ddd; background:#fff; font-size:12px; color:#333; margin-left:6px; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="top">
      <div class="title">
        <h1>{escape_html(title_text)}</h1>
        <p>{escape_html(t(lang, "subtitle"))}</p>
        <div class="pills">{pills}</div>
      </div>
      <div class="panel" style="margin-top:0;">
        {region_text_html}
        <div style="height:8px;"></div>
        <div class="meta"><strong>{t(lang, "language_label")}:</strong></div>
        <div class="langs">
          {build_lang_switch(region, lang, presentation)}
        </div>
        <div style="height:10px;"></div>
        <div class="meta">
          {admin_link_html}
          <a class="link" href="/cards?region={region}&lang={lang}&presentation={presentation}">{t(lang, "cards_link")}</a>
        </div>
      </div>
    </div>

    {pres_banner}

    {english_note_html}

    <div class="panel">
      <h2 style="margin:0 0 6px;">{t(lang, "ask_title")}</h2>
      <div class="meta">{t(lang, "ask_hint")}</div>
      <div style="height:10px;"></div>
      <label for="q">{t(lang, "ask_title")}</label>
      <textarea id="q" placeholder="{escape_html(t(lang, "ask_placeholder"))}"></textarea>
      <div style="height:12px;"></div>
      <div class="row">
        <button class="primary" onclick="ask()">{t(lang, "ask_button")}</button>
        <div class="meta" id="status"></div>
      </div>
      <div class="err" id="err"></div>
    </div>

    {examples_panel(region, lang) if pres_on else ""}

    <div class="panel">
      <h2 style="margin:0;">{t(lang, "results_title")}</h2>
      <div id="moreWrap" style="display:none;"></div>
      <div class="cards" id="cards"></div>
      <div class="meta" id="empty" style="margin-top:10px;"></div>
      <div class="small" id="fallback" style="margin-top:10px; color:#555;"></div>
    </div>

    {safety_panel(lang)}

    {latest_cards_panel(db_path, region, lang, presentation)}

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
    document.getElementById("moreWrap").innerHTML = "";
    document.getElementById("moreWrap").style.display = "none";
    document.getElementById("empty").textContent = "";
    document.getElementById("fallback").textContent = "";

    const res = await fetch("/ask", {{
      method: "POST",
      headers: {{ "Content-Type": "application/json" }},
      body: JSON.stringify({{
        question: q,
        region: "{region}",
        lang: "{lang}",
        presentation: "{presentation}"
      }})
    }});

    const data = await res.json();
    document.getElementById("status").textContent = "";

    if (!res.ok) {{
      document.getElementById("err").textContent = "{t(lang, "error_prefix")}: " + (data.detail || "Unknown error");
      return;
    }}

    if (!data.matches || data.matches.length === 0) {{
      document.getElementById("empty").textContent = "{t(lang, "no_results")}";
      if ("{presentation}" === "1") {{
        document.getElementById("fallback").textContent = "{t(lang, "fallback_note")}";
      }}
      return;
    }}

    // B behavior: show Top-3; remaining (up to 2) behind "Show more"
    const visible = data.matches.slice(0, {TOP_VISIBLE});
    const hidden = data.matches.slice({TOP_VISIBLE});

    for (const m of visible) {{
      document.getElementById("cards").appendChild(renderCard(m, false));
    }}

    if (hidden.length > 0) {{
      const btn = document.createElement("button");
      btn.className = "secondary";
      btn.type = "button";
      btn.textContent = "{t(lang, "show_more")} (" + hidden.length + ")";
      btn.style.marginTop = "12px";

      const container = document.getElementById("moreWrap");
      container.style.display = "block";
      container.appendChild(btn);

      const hiddenGrid = document.createElement("div");
      hiddenGrid.className = "cards";
      hiddenGrid.style.marginTop = "12px";
      hiddenGrid.style.display = "none";
      container.appendChild(hiddenGrid);

      for (const m of hidden) {{
        hiddenGrid.appendChild(renderCard(m, true));
      }}

      btn.onclick = () => {{
        hiddenGrid.style.display = "grid";
        btn.remove();
      }};
    }}

    if ("{presentation}" === "1") {{
      document.getElementById("fallback").textContent = "{t(lang, "fallback_note")}";
    }}
  }}

  function renderCard(m, lowRef) {{
    const div = document.createElement("div");
    div.className = "card";

    const conf = confidenceLabel(m.score, lowRef);

    div.innerHTML = `
      <h3>${{escapeHtml(m.title)}}
        <span class="badge">{t(lang, "confidence")}: ${{escapeHtml(conf)}}</span>
      </h3>
      <div class="small"><strong>{t(lang, "score")}:</strong> ${{m.score}}</div>
      <div class="small"><strong>{t(lang, "category")}:</strong> ${{escapeHtml(m.category)}}</div>
      <div class="small"><strong>{t(lang, "tags")}:</strong> ${{escapeHtml(m.tags)}}</div>
      <div style="height:8px;"></div>
      <div>${{escapeHtml(m.content)}}</div>
      <div class="why"><strong>{t(lang, "why_this_match")}:</strong><br/>${{escapeHtml(m.why.join(" · "))}}</div>
    `;
    return div;
  }}

  function confidenceLabel(score, lowRef) {{
    if (lowRef) return "{t(lang, "low_ref")}";
    if (score >= 30) return "{t(lang, "high_conf")}";
    if (score >= 22) return "{t(lang, "med_conf")}";
    return "{t(lang, "low_conf")}";
  }}

  function useExample(text) {{
    const box = document.getElementById("q");
    box.value = text;
    box.focus();
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
    presentation = request.query_params.get("presentation", "1")
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

    db_path = pick_db_path(presentation)

    conn = db(db_path)
    cur = conn.cursor()

    # Demo mode: show only region cards to avoid confusion
    if presentation == "1":
        clause, params = _region_clause(region)
        cur.execute(f"SELECT * FROM experiences WHERE {clause} ORDER BY id DESC LIMIT 200", params)
    else:
        cur.execute("SELECT * FROM experiences ORDER BY id DESC LIMIT 200")

    rows = cur.fetchall()
    conn.close()

    items = ""
    for r in rows:
        items += f"""
        <div class="card">
          <h3>{escape_html(r["title"])}</h3>
          <div class="small"><strong>{t(lang,"category")}:</strong> {escape_html(r["category"])}</div>
          <div class="small"><strong>{t(lang,"tags")}:</strong> {escape_html(r["tags"])}</div>
          <div style="height:8px;"></div>
          <div>{escape_html(r["content"])}</div>
        </div>
        """

    html = f"""
<!doctype html>
<html lang="{lang}">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape_html(t(lang,"cards_title"))}</title>
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
      <h1 style="margin:0;">{escape_html(t(lang,"cards_title"))}</h1>
      <p style="margin:6px 0 0;color:#444;">{escape_html(t(lang,"cards_subtitle"))}</p>
      <p style="margin:10px 0 0;">
        <a class="link" href="/?region={region}&lang={lang}&presentation={presentation}">{escape_html(t(lang,"back_home"))}</a>
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

    # Admin is only available in normal mode
    if presentation == "1":
        return RedirectResponse(url=f"/?region={region}&lang={lang}&presentation=1", status_code=303)

    if region not in ("ca", "us"):
        region = "ca"
    if lang not in REGION_LANGS.get(region, ["en"]):
        lang = "en"

    conn = db(APP_DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT * FROM experiences ORDER BY id DESC LIMIT 30")
    rows = cur.fetchall()
    conn.close()

    options = []
    for l in ["en", "fr", "es"]:
        options.append(f'<option value="{l}">{escape_html(t(lang, "lang_"+l))}</option>')
    options_html = "\n".join(options)

    items = ""
    for r in rows:
        items += f"""
        <div class="card">
          <h3>{escape_html(r["title"])}</h3>
          <div class="small"><strong>{t(lang, "category")}:</strong> {escape_html(r["category"])}</div>
          <div class="small"><strong>{t(lang, "tags")}:</strong> {escape_html(r["tags"])}</div>
          <div style="height:8px;"></div>
          <div>{escape_html(r["content"])}</div>
        </div>
        """

    html = f"""
<!doctype html>
<html lang="{lang}">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape_html(t(lang, "admin_title"))}</title>
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
      <h1 style="margin:0;">{escape_html(t(lang, "admin_title"))}</h1>
      <p style="margin:6px 0 0;color:#444;">{escape_html(t(lang, "admin_subtitle"))}</p>
      <p style="margin:10px 0 0;">
        <a class="link" href="/?region={region}&lang={lang}&presentation=0">{escape_html(t(lang, "back_home"))}</a>
        &nbsp;•&nbsp;
        <a class="link" href="/cards?region={region}&lang={lang}&presentation=0">{escape_html(t(lang, "cards_link"))}</a>
      </p>
    </div>

    <div class="panel">
      <form method="post" action="/admin/add?region={region}&lang={lang}&presentation=0">
        <label>{escape_html(t(lang, "field_title"))}</label>
        <input name="title" required />

        <label>{escape_html(t(lang, "field_category"))}</label>
        <input name="category" required placeholder="e.g., Onboarding, Digital Access, Transfers, Payments, Cards, Fraud/Scam, Fees, Statements, Support" />

        <label>{escape_html(t(lang, "field_tags"))}</label>
        <input name="tags" required placeholder="e.g., login, password, transfer, pending, scam, fees" />

        <label>{escape_html(t(lang, "field_language"))}</label>
        <select name="content_lang">
          {options_html}
        </select>

        <label>{escape_html(t(lang, "field_content"))}</label>
        <textarea name="content" required></textarea>

        <button type="submit">{escape_html(t(lang, "save_button"))}</button>
      </form>
    </div>

    <div class="panel">
      <h2 style="margin:0 0 10px;">{escape_html(t(lang, "latest_cards"))}</h2>
      <div class="cards">
        {items if items else "<div class='small'>No cards yet.</div>"}
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

    if presentation == "1":
        raise HTTPException(status_code=403, detail="Admin is disabled in presentation mode.")

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

    conn = db(APP_DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO experiences (title, category, tags, content, content_lang, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (title, category, tags, content, content_lang, created_at),
    )
    conn.commit()
    conn.close()

    return RedirectResponse(url=f"/admin?region={region}&lang={lang}&presentation=0", status_code=303)


@app.post("/ask")
def ask(payload: Dict[str, Any]):
    question = normalize(payload.get("question", ""))
    region = (payload.get("region", "ca") or "ca").lower()
    lang = (payload.get("lang", "en") or "en").lower()
    presentation = (payload.get("presentation", "0") or "0")

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

    db_path = pick_db_path(presentation)
    demo_region_filter = (presentation == "1")
    matches = get_top_matches(db_path, question, region=region, demo_region_filter=demo_region_filter, limit=MAX_MATCHES)
    return JSONResponse({"question": question, "matches": matches})



