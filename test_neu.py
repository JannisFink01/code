# test_neu.py
# Evaluation des sokratischen Tutors (Z-Diode)
# Ausführung: python test_neu.py
import csv
import os
from openai import OpenAI
from deepeval import evaluate
from evaluation import run_evaluation, startup_check
from config import (
    TUTOR_MODEL,
    SIMULATOR_MODEL,
    JUDGE_MODEL,
    KONTEXT_FILE,
)

try:
    from deepeval.metrics import ConversationRelevancyMetric as RelevancyMetric
except ImportError:
    from deepeval.metrics import TurnRelevancyMetric as _RelevancyMetric


from rate_limiter import RateLimiter
from gwdg_model import GWDGModel

# =============================================================
# KONFIGURATION
# ==========================================================
PROMPT_VERSION = os.getenv("PROMPT_VERSION", "v1")

with open(KONTEXT_FILE, encoding="utf-8") as f:
    CONTEXT = f.read()
with open("system_prompt.txt", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()

# Gemeinsamer Rate Limiter für alle Modelle
rate_limiter = RateLimiter(calls_per_second=2, calls_per_minute=15)
judge_llm = GWDGModel(JUDGE_MODEL, rate_limiter=rate_limiter)
simulator_llm = GWDGModel(SIMULATOR_MODEL, rate_limiter=rate_limiter)

# Tutor-Client
tutor_llm = GWDGModel(TUTOR_MODEL, rate_limiter=rate_limiter)


# =============================================================
# STARTUP CHECK
# =============================================================


def startup_check() -> bool:
    print("\n[Startup Check]")
    api_key = os.getenv("GWDG_API_KEY")
    base_url = os.getenv("GWDG_BASE_URL")

    print(f"  GWDG_API_KEY:  {'✓ gesetzt' if api_key else '✗ FEHLT'}")
    print(f"  GWDG_BASE_URL: {repr(base_url)}")

    if not api_key:
        print("  ✗ FEHLER: GWDG_API_KEY fehlt in .env")
        return False
    if base_url and "/chat/completions" in base_url:
        print("  ✗ FEHLER: GWDG_BASE_URL darf nicht '/chat/completions' enthalten!")
        return False

    print("  Teste API-Verbindung...")
    try:
        test_client = OpenAI(api_key=api_key, base_url=base_url)
        test_client.chat.completions.create(
            model=SIMULATOR_MODEL,
            messages=[{"role": "user", "content": "Hallo"}],
            max_tokens=10,
        )
        print("  ✓ Verbindung OK")
    except Exception as e:
        print(f"  ✗ Verbindung FEHLER: {e}")
        return False

    for fname in ["system_prompt.txt", "kontext.txt"]:
        if not os.path.exists(fname):
            print(f"  ✗ Datei fehlt: {fname}")
            return False
        print(f"  ✓ {fname}")

    print("[Startup Check] Alles OK – starte Tests\n")
    return True


# =============================================================
# MAIN
# =============================================================


def main():
    PROMPT_RUNS = [
        ("prompts/system_prompt.txt", "system_prompt"),
        ("prompts/minimaler_sokrat.txt", "minimaler_sokrat"),
        ("prompts/system_prompt_context.txt", "system_prompt_context"),
        ("prompts/minimaler_sokrat_context.txt", "minimaler_sokrat_context"),
        ("prompts/no_Prompt.txt", "no_Prompt"),
    ]
    for prompt_file, version in PROMPT_RUNS:
        if not os.path.exists(prompt_file):
            print(f"  ✗ {prompt_file} nicht gefunden – überspringe")
            continue
        run_evaluation(prompt_file, version)

    print(f"\n{'='*60}")
    print(f"  Alle {len(PROMPT_RUNS)} Durchgänge abgeschlossen!")
    print(f"{'='*60}")

    combined_path = "eval_rohdaten_alle.csv"
    fieldnames = ["prompt_version", "topic", "level", "behavior",
                  "repeat", "metric", "score", "success", "reason"]

    with open(combined_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for _, version in PROMPT_RUNS:
            raw_file = f"eval_rohdaten_{version}.csv"
            if os.path.exists(raw_file):
                with open(raw_file, "r", encoding="utf-8-sig") as rf:
                    reader = csv.DictReader(rf)
                    for row in reader:
                        w.writerow(row)

    print(f"  Kombiniert → {combined_path}")

if __name__ == "__main__":
    if startup_check():
        main()
    else:
        print("\n[Abbruch] Bitte Fehler beheben und erneut starten.")
