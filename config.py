# config.py
# Zentrale Konfiguration – alle Einstellungen an einem Ort
# Wird von test_neu.py, gwdg_model.py und rate_limiter.py importiert

from dotenv import load_dotenv
import os

load_dotenv()

# =============================================================
# API
# =============================================================
GWDG_API_KEY = os.getenv("GWDG_API_KEY")
GWDG_BASE_URL = os.getenv("GWDG_BASE_URL", "https://chat-ai.academiccloud.de/v1")

# =============================================================
# MODELLE
# =============================================================
TUTOR_MODEL = os.getenv("TUTOR_MODEL", "gemma-4-31b-it")
SIMULATOR_MODEL = os.getenv("SIMULATOR_MODEL", "meta-llama-3.1-8b-instruct")
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "openai-gpt-oss-120b")

# =============================================================
# RATE LIMITER
# =============================================================
RATE_CALLS_PER_SECOND = int(os.getenv("RATE_CALLS_PER_SECOND", "2"))
RATE_CALLS_PER_MINUTE = int(os.getenv("RATE_CALLS_PER_MINUTE", "15"))
RETRY_WAIT_SECONDS = int(os.getenv("RETRY_WAIT_SECONDS", "45"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "5"))

# =============================================================
# EVALUATION
# =============================================================
REPEATS = int(os.getenv("REPEATS", "3"))
MAX_USER_SIMULATIONS = int(os.getenv("MAX_USER_SIMULATIONS", "2"))
THRESHOLD = float(os.getenv("THRESHOLD", "0.7"))
PROMPT_VERSION = os.getenv("PROMPT_VERSION", "v1")

# =============================================================
# DATEIPFADE
# =============================================================
SYSTEM_PROMPT_FILE = os.getenv("SYSTEM_PROMPT_FILE", "system_prompt.txt")
KONTEXT_FILE = os.getenv("KONTEXT_FILE", "kontext.txt")
OUTPUT_RAW = f"eval_rohdaten_{PROMPT_VERSION}.csv"
OUTPUT_AGG = f"eval_aggregat_{PROMPT_VERSION}.csv"


# =============================================================
# VALIDIERUNG
# =============================================================
def validate():
    """Prüft ob alle Pflichtfelder gesetzt sind."""
    errors = []
    if not GWDG_API_KEY:
        errors.append("GWDG_API_KEY fehlt in .env")
    if not GWDG_BASE_URL:
        errors.append("GWDG_BASE_URL fehlt in .env")
    if "/chat/completions" in (GWDG_BASE_URL or ""):
        errors.append("GWDG_BASE_URL darf nicht '/chat/completions' enthalten")
    if not os.path.exists(SYSTEM_PROMPT_FILE):
        errors.append(f"Datei nicht gefunden: {SYSTEM_PROMPT_FILE}")
    if not os.path.exists(KONTEXT_FILE):
        errors.append(f"Datei nicht gefunden: {KONTEXT_FILE}")
    return errors
