# evaluation.py
"""Bewertet bereits simulierte Konversationen einer Prompt-Version: pro Konversation
alle Metriken berechnen (mit Resume + Retry) und die Ergebnisse als Rohdaten- sowie
Aggregat-CSV ablegen. Die Simulation selbst liegt in simulation.py – diese Datei
holt die Gespraeche nur ueber simulate_conversations() (Cache-aware) und wertet sie aus.
"""
import os
import csv
from retry_utils import retry_sync
from collections import defaultdict
from config import (
    BASE_WAIT,
    FIELDNAMES,
    RUN_EVALUATION,
    conv_path,
    agg_path,
    raw_path,
    MAX_RETRIES,
)
from clients import judge_llm
from metrics import build_metrics
from persistence import attach_results
from simulation import simulate_conversations

def _evaluate_single(tc, metrics, meta, version):
    """Berechnet alle uebergebenen Metriken fuer genau eine Konversation.
 
    Ruft fuer jede Metrik `metric.measure(tc)` auf (mit Retry) und liefert pro
    Metrik eine Ergebniszeile. Scheitert eine Metrik endgueltig, wird eine
    Fehlerzeile (score=None) geschrieben, statt sie stumm zu verwerfen.
 
    Args:
        tc: Die zu bewertende `ConversationalTestCase`.
        metrics: Liste der Metrik-Objekte (siehe `metrics.build_metrics`).
        meta: Dict mit Szenario-Infos (topic/level/behavior/repeat/conversation_id).
        version: Kurzname der laufenden Prompt-Version.
 
    Returns:
        Liste von Dicts (eines pro Metrik), passend zu `config.FIELDNAMES`.
    """
    results = []
    for metric in metrics:
        metric_name = getattr(metric, "__name__", "?")                
        # gemeinsame Felder fuer Erfolg wie Fehler
        base = {
            "prompt_version": version,
            "conversation_id": meta.get("conversation_id", ""),
            "topic": meta.get("topic", ""),
            "level": meta.get("level", ""),
            "behavior": meta.get("behavior", ""),
            "repeat": meta.get("repeat", ""),
            "metric": metric_name,
        }
        try:
            retry_sync(
                metric.measure,
                tc,
                max_retries=MAX_RETRIES,
                base_wait=BASE_WAIT,
                retryable=lambda e: True,
                label=metric_name,
            )
            results.append(
                {
                    **base,
                    "score": metric.score,
                    "success": (
                        metric.score >= metric.threshold
                        if metric.score is not None
                        else None
                    ),
                    "reason": (metric.reason or "").replace("\n", " "),
                    "verbose_logs": getattr(metric, "verbose_logs", None),
                }
            )
        except Exception as e:
            print(f"    ⚠ {metric_name} übersprungen – {type(e).__name__}: {e}")
            results.append(
                {
                    **base,
                    "score": None,
                    "success": None,
                    "reason": f"ERROR: {type(e).__name__}: {e}",
                    "verbose_logs": getattr(metric, "verbose_logs", None),
                }
            )
    return results


def run_evaluation(prompt_file: str, version: str):
    """Fuehrt einen kompletten Evaluierungslauf fuer eine Prompt-Version durch.
 
    Ablauf:
    1. Konversationen ueber simulate_conversations() holen (simuliert neu oder
       laedt aus dem Cache – Doppel-Simulations-Schutz liegt dort).
    2. Fuer jede noch nicht evaluierte Konversation alle Metriken berechnen und
       die Zeilen fortlaufend (Resume-faehig) in die Rohdaten-CSV schreiben.
    3. Aggregat (Mittelwert/Pass-Rate je Behavior+Metrik) berechnen und schreiben.
    4. Ergebnisse pro conversation_id an die Konversations-JSON anhaengen.
 
    Args:
        prompt_file: Pfad zur Prompt-Textdatei.
        version: Kurzname der Prompt-Version (bestimmt die Ausgabedateipfade).
    """
    print(f"\n{'='*60}")
    print(f"  Starte Evaluation: {version} ({prompt_file})")
    print(f"{'='*60}")
    r_path = raw_path(version)
    a_path = agg_path(version)
    c_path = conv_path(version)
    
    # =========================================================
    # KONVERSATIONEN HOLEN (Simulation oder Cache – in simulation.py)
    # =========================================================
    test_cases, metadata = simulate_conversations(prompt_file, version)
    if not RUN_EVALUATION:
        print("  RUN_EVALUATION=false → nur Konversationen erzeugt, keine Bewertung.")
        return
    # =========================================================
    # RESUME-CHECK: bereits evaluierte Testfälle ermitteln
    # =========================================================
    already_done = set()
    if os.path.exists(r_path):
        with open(r_path, "r", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                key = (
                    row.get("topic", ""),
                    row.get("behavior", ""),
                    row.get("repeat", ""),
                )
                already_done.add(key)
        print(f"  {len(already_done)} Testfälle bereits evaluiert – setze fort.")
    else:
        with open(r_path, "w", newline="", encoding="utf-8-sig") as f:
            csv.DictWriter(f, fieldnames=FIELDNAMES).writeheader()

    # =========================================================
    # EVALUATION (sequenziell, mit Resume + Retry)
    # =========================================================
    print(f"\n  {len(test_cases)} Testfälle evaluieren...")
    metrics = build_metrics(judge_llm)
    rows = []
    skipped = 0
    for i, tc in enumerate(test_cases):
        meta = metadata[i] if i < len(metadata) else {}
        key = (
            meta.get("topic", ""),
            meta.get("behavior", ""),
            str(meta.get("repeat", "")),
        )
        if key in already_done:
            skipped += 1
            continue
        print(
            f"  [{i+1}/{len(test_cases)}] {meta.get('topic','?')[:35]} | {meta.get('behavior','?')[:25]}"
        )
        new_rows = _evaluate_single(tc, metrics, meta, version)
        for row in new_rows:
            rows.append(row)
            with open(r_path, "a", newline="", encoding="utf-8-sig") as f:
                csv.DictWriter(f, fieldnames=FIELDNAMES).writerow(row)
        print(f"    ✓ fertig")

    evaluated = len(test_cases) - skipped
    print(f"\n  {evaluated} neu evaluiert | {skipped} übersprungen")

    # =========================================================
    # AGGREGAT
    # =========================================================
    all_rows = []
    with open(r_path, "r", encoding="utf-8-sig") as f:
        all_rows = list(csv.DictReader(f))

    agg = defaultdict(list)
    for r in all_rows:
        score = r.get("score")
        if score is not None and score != "":
            agg[(r["behavior"], r["metric"])].append(
                (float(score), r.get("success") == "True")
            )

    with open(a_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["behavior", "metric", "avg_score", "pass_rate", "n"])
        for (behavior, metric), vals in sorted(agg.items()):
            scores = [v[0] for v in vals]
            passes = [1 for v in vals if v[1]]
            w.writerow(
                [
                    behavior,
                    metric,
                    round(sum(scores) / len(scores), 3),
                    round(len(passes) / len(vals), 3),
                    len(vals),
                ]
            )

    print(f"\n  Rohdaten → {r_path}")
    print(f"  Aggregat → {a_path}")
    # =========================================================
    # ERGEBNISSE PRO conversation_id an die Konversations-JSON anhaengen
    # =========================================================
    by_id = defaultdict(list)
    for r in all_rows:
        if r.get("conversation_id"):
            by_id[r["conversation_id"]].append(r)
    attach_results(c_path, by_id)
