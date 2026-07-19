import os
# config.py
# Zentrale Konfiguration – alle Einstellungen an einem Ort
# Wird von test_neu.py, gwdg_model.py und rate_limiter.py importiert

from dotenv import load_dotenv

load_dotenv()

# =============================================================
# API
# =============================================================
GWDG_API_KEY = os.getenv("GWDG_API_KEY")
GWDG_BASE_URL = os.getenv("GWDG_BASE_URL", "https://chat-ai.academiccloud.de/v1")
OPENWEBUI_API_KEY = os.getenv("OPENWEBUI_API_KEY")
OPENWEBUI_BASE_URL = os.getenv("OPENWEBUI_BASE_URL")
RAG_VERIFY_SSL =False
# =============================================================
# MODELLE
# =============================================================
TUTOR_MODEL = os.getenv("TUTOR_MODEL", "gemma-4-31b-it")
SIMULATOR_MODEL = os.getenv("SIMULATOR_MODEL", "meta-llama-3.1-8b-instruct")
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "openai-gpt-oss-120b")
RAG_MODEL = os.getenv("RAG_MODEL", "qdrant_openwebui_rag_pipeline_rerank_moodle")
# =============================================================
# RATE LIMITER
# =============================================================
RATE_CALLS_PER_SECOND = int(os.getenv("RATE_CALLS_PER_SECOND", "2"))
RATE_CALLS_PER_MINUTE = int(os.getenv("RATE_CALLS_PER_MINUTE", "15"))
RETRY_WAIT_SECONDS = int(os.getenv("RETRY_WAIT_SECONDS", "60"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "10"))
BASE_WAIT = int(os.getenv("BASE_WAIT", "45"))
CAP = int(os.getenv("CAP", "180"))

# =============================================================
# EVALUATION
# =============================================================
CHATBOT_ROLE = "Sokrat: ein sokratischer Tutor, der mit Rückfragen führt und die Lösung nie direkt verrät."
REPEATS = int(os.getenv("REPEATS", "1"))
MAX_USER_SIMULATIONS = int(os.getenv("MAX_USER_SIMULATIONS", "6"))
THRESHOLD = float(os.getenv("THRESHOLD", "0.7"))
PROMPT_VERSION = os.getenv("PROMPT_VERSION", "v1")
PROMPT_RUNS = [
    ("prompts/system_prompt.txt", "system_prompt"),
    ("prompts/minimaler_sokrat.txt", "minimaler_sokrat"),
    ("prompts/system_prompt_context.txt", "system_prompt_context"),
    ("prompts/minimaler_sokrat_context.txt", "minimaler_sokrat_context"),
    ("prompts/no_Prompt.txt", "no_Prompt"),
]
# =============================================================
# DATEIPFADE
# =============================================================
SYSTEM_PROMPT_FILE = os.getenv("SYSTEM_PROMPT_FILE", "system_prompt.txt")
KONTEXT_FILE = os.getenv("KONTEXT_FILE", "kontext.txt")
OUTPUT_RAW = f"eval_rohdaten_{PROMPT_VERSION}.csv"
OUTPUT_AGG = f"eval_aggregat_{PROMPT_VERSION}.csv"
FIELDNAMES = [
    "prompt_version",
    "topic",
    "level",
    "behavior",
    "repeat",
    "metric",
    "score",
    "success",
    "reason",
    "verbose_logs",
]
# =============================================================
# PERSISTENCE_PATHS
# =============================================================

PERSISTENCE_DIR = "persistence"
CSV_DIR = f"{PERSISTENCE_DIR}/csv"
CONV_DIR = f"{PERSISTENCE_DIR}/konversationen"
COMBINED_PATH = f"{CSV_DIR}/eval_rohdaten_alle.csv"


def raw_path(version):
    return f"{CSV_DIR}/eval_rohdaten_{version}.csv"


def agg_path(version):
    return f"{CSV_DIR}/eval_aggregat_{version}.csv"


def conv_path(version):
    return f"{CONV_DIR}/konversationen_{version}.json"


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
    if "/api/chat/completions" in (OPENWEBUI_BASE_URL or ""):
        errors.append("OPENWEBUI_BASE_URL darf nicht '/api/chat/completions' enthalten")
    return errors

# =============================================================
# MODELLKONFIGURATION
# =============================================================
RAG_CONFIG = {
    "collections": "hollstein_collection_labor, hollstein_collection_vorlesung",
    "retrieval": "dense, sparse",
    "is_cross_encoder_rerank": False,
}

RUN_EVALUATION = os.getenv("RUN_EVALUATION", "true").lower() == "true"