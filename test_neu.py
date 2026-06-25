# test_neu.py
# Evaluation des sokratischen Tutors (Z-Diode)
# Ausführung: python test_neu.py
import csv
import os
from openai import OpenAI
from deepeval import evaluate
from evaluation import run_evaluation
from config import (
    GWDG_BASE_URL,
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
from config import PROMPT_RUNS, CHATBOT_ROLE, GWDG_API_KEY, GWDG_BASE_URL

# =============================================================
# KONFIGURATION
# ==========================================================

with open(KONTEXT_FILE, encoding="utf-8") as f:
    CONTEXT = f.read()
with open("prompts/system_prompt.txt", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()

# =============================================================
# STARTUP CHECK
# =============================================================


def startup_check() -> bool:
    print("\n[Startup Check]")
    print(f"  GWDG_API_KEY:  {'✓ gesetzt' if GWDG_API_KEY else '✗ FEHLT'}")
    print(f"  GWDG_BASE_URL: {repr(GWDG_BASE_URL)}")

    if not GWDG_API_KEY:
        print("  ✗ FEHLER: GWDG_API_KEY fehlt in .env")
        return False
    if "/chat/completions" in (GWDG_BASE_URL or ""):
        print("  ✗ FEHLER: GWDG_BASE_URL falsch")
        return False

    print("  Teste API-Verbindung...")
    for attempt in range(1, 4):
        try:
            test_client = OpenAI(api_key=GWDG_API_KEY, base_url=GWDG_BASE_URL)
            test_client.chat.completions.create(
                model=SIMULATOR_MODEL,
                messages=[{"role": "user", "content": "Hallo"}],
                max_tokens=10,
            )
            print("  ✓ Verbindung OK")
            break
        except Exception as e:
            if attempt < 3:
                print(f"  ⟳ Versuch {attempt}/3 fehlgeschlagen ({e}) – warte 30s...")
                import time

                time.sleep(30)
            else:
                print(f"  ✗ Verbindung nach 3 Versuchen fehlgeschlagen: {e}")
                return False

    for prompt_file, _ in PROMPT_RUNS:
        if not os.path.exists(prompt_file):
            print(f"  ✗ {prompt_file} nicht gefunden")
            return False
        print(f"  ✓ {prompt_file}")

    print("[Startup Check] Alles OK\n")
    return True


# =============================================================
# MAIN
# =============================================================


def main():

    for prompt_file, version in PROMPT_RUNS:
        if not os.path.exists(prompt_file):
            print(f"  ✗ {prompt_file} nicht gefunden – überspringe")
            continue
        run_evaluation(prompt_file, version)

    print(f"\n{'='*60}")
    print(f"  Alle {len(PROMPT_RUNS)} Durchgänge abgeschlossen!")
    print(f"{'='*60}")

    combined_path = "eval_rohdaten_alle.csv"
    fieldnames = [
        "prompt_version",
        "topic",
        "level",
        "behavior",
        "repeat",
        "metric",
        "score",
        "success",
        "reason",
    ]

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
