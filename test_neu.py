# test_neu.py
# Einstiegspunkt fuer die Evaluation des sokratischen RAG-Tutors.
#
#   python test_neu.py rq1    -> RQ1: verschiedene Prompts, EINE RAG-Konfig (sokratische Qualitaet)
#   python test_neu.py rq2    -> RQ2: EIN Prompt, verschiedene RAG-Konfigs (Retrieval-Qualitaet)
#   python test_neu.py both   -> beides nacheinander
#
# RQ1 und RQ2 sind bewusst getrennt: eigene Konversations-Caches, eigene CSVs,
# eigene Auswertung (rq1_prompt_auswertung.csv bzw. rq2_rag_auswertung.csv).

import os
import sys
import datetime

# ---------- Logging: alle Ausgaben zusaetzlich in eine Datei ----------
os.makedirs("logs", exist_ok=True)
_logpath = f"logs/lauf_{datetime.datetime.now():%Y%m%d_%H%M%S}.log"
_logfile = open(_logpath, "w", encoding="utf-8")

class _Tee:
    def __init__(self, *streams): self.streams = streams
    def write(self, s):
        for st in self.streams:
            st.write(s); st.flush()
    def flush(self):
        for st in self.streams: st.flush()

sys.stdout = _Tee(sys.stdout, _logfile)
sys.stderr = _Tee(sys.stderr, _logfile)
print(f"[Log] Schreibe nach {_logpath}")

from evaluation import run_evaluation
from clients import simulator_llm, judge_llm
from auswertung import auswerten
from config import PROMPT_RUNS, RAG_CONFIGS, JUDGE_BASE_URL, JUDGE_API_KEY

# feste RAG-Konfiguration fuer RQ1 (Prompt-Vergleich)
RQ1_CONFIG = RAG_CONFIGS["dense_rerank"]
# fester (sokratischer) Prompt fuer RQ2 (Konfig-Vergleich)
RQ2_PROMPT = ("prompts/minimaler_sokrat.txt", "minimaler_sokrat")


# =============================================================
# STARTUP CHECK
# =============================================================
def startup_check() -> bool:
    """Prueft Modell-Erreichbarkeit (Simulator + Judge) und Prompt-Dateien."""
    print("\n[Startup Check]")
    print(f"  Judge:     {judge_llm.model_name} -> {judge_llm._client.base_url}")
    print(f"  Simulator: {simulator_llm.model_name} -> {simulator_llm._client.base_url}")
    if not JUDGE_API_KEY:
        print("  ✗ JUDGE/LOCAL API-Key fehlt in .env"); return False
    if not JUDGE_BASE_URL:
        print("  ✗ JUDGE/LOCAL URL fehlt in .env"); return False
    try:
        simulator_llm.generate("Antworte nur mit OK.")
        judge_llm.generate("Antworte nur mit OK.")
        print("  ✓ Simulator + Judge erreichbar")
    except Exception as e:
        print(f"  ✗ Verbindung fehlgeschlagen: {type(e).__name__}: {e}")
        return False
    for prompt_file, _ in PROMPT_RUNS:
        if not os.path.exists(prompt_file):
            print(f"  ✗ {prompt_file} nicht gefunden"); return False
        print(f"  ✓ {prompt_file}")
    print("[Startup Check] Alles OK\n")
    return True


# =============================================================
# RQ1 / RQ2
# =============================================================
def run_rq1():
    """RQ1: verschiedene Prompts, EINE RAG-Konfiguration -> sokratische Qualitaet (GEval)."""
    print("\n### RQ1: Prompt-Vergleich ###")
    for prompt_file, version in PROMPT_RUNS:
        if not os.path.exists(prompt_file):
            print(f"  ✗ {prompt_file} fehlt – uebersprungen"); continue
        run_evaluation(prompt_file, version, RQ1_CONFIG)
    auswerten()   # -> rq1_prompt_auswertung.csv (Versionen ohne '__')


def run_rq2():
    """RQ2: EIN Prompt, verschiedene RAG-Konfigurationen -> Retrieval-Qualitaet (native)."""
    print("\n### RQ2: RAG-Konfigurations-Vergleich ###")
    prompt_file, base = RQ2_PROMPT
    for cfg_name, cfg in RAG_CONFIGS.items():
        run_evaluation(prompt_file, f"{base}__{cfg_name}", cfg)
    auswerten()   # -> rq2_rag_auswertung.csv (Versionen mit '__')


# =============================================================
# EINSTIEGSPUNKT
# =============================================================
if __name__ == "__main__":
    if not startup_check():
        print("\n[Abbruch] Bitte Fehler beheben und erneut starten.")
        sys.exit(1)

    modus = sys.argv[1] if len(sys.argv) > 1 else "rq1"
    if modus == "rq1":
        run_rq1()
    elif modus == "rq2":
        run_rq2()
    elif modus == "both":
        run_rq1(); run_rq2()
    else:
        print(f"Unbekannter Modus '{modus}'. Nutze: rq1 | rq2 | both")