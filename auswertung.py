# auswertung.py
# Wertet die Rohdaten getrennt nach Forschungsfrage aus:
#
#   RQ1 (Prompt-Effekt, sokratische Qualitaet)  -> nur die GEval-Metriken
#        - gewichteter sokratischer Score je Gespraech, gemittelt je Prompt-Version
#        - Gate-Compliance-Rate (Lösungstreue & Korrektheit) je Prompt-Version
#        - Mittelwert je einzelner GEval-Metrik
#
#   RQ2 (RAG-Konfig-Effekt, Retrieval-Qualitaet) -> die nativen RAG-Metriken
#        - Mittelwerte von TurnContextualRelevancy und TurnFaithfulness je Konfiguration
#
# Unterscheidung: Prompt-Versionen mit "__" im Namen (z. B. "minimaler_sokrat__dense_rerank")
# gehoeren zu RQ2 (base__config); ohne "__" zu RQ1.
#
# Aufruf:
#   python auswertung.py persistence/csv/eval_rohdaten_*.csv
#   (oder ohne Argument: sucht persistence/csv/eval_rohdaten_*.csv)

import csv
import sys
import glob
import statistics as st
from collections import defaultdict

csv.field_size_limit(100_000_000)

GATE_THRESHOLD = 0.5
GEWICHTE = {
    "Lösung nicht verraten":            0.25,
    "Fachliche Korrektheit":            0.15,
    "Sokratische Rückfragen":           0.20,
    "Schrittweise Lernprogression":     0.15,
    "Niveau-Anpassung":                 0.10,
    "Verständnisförderung / Transfer":  0.10,
    "Respektvolle Kommunikation":       0.05,
}
GATE_METRIKEN = ["Lösung nicht verraten", "Fachliche Korrektheit"]
GEVAL_METRIKEN = list(GEWICHTE.keys())
RAG_METRIKEN = ["Turn Contextual Relevancy", "Turn Faithfulness"]


def kurz(m):
    return m.replace("[GEval]", "").replace(" [Conversational GEval]", "").strip()


def lade(pfade):
    rows = []
    for p in pfade:
        rows += list(csv.DictReader(open(p, encoding="utf-8-sig")))
    return rows


def gewichteter_score(scores):
    s = g = 0.0
    for name, w in GEWICHTE.items():
        v = scores.get(name)
        if v is not None:
            s += w * v; g += w
    return s / g if g else None


def gate_ok(scores):
    for m in GATE_METRIKEN:
        v = scores.get(m)
        if v is not None and v < GATE_THRESHOLD:
            return False
    return True


def mittel(xs):
    xs = [x for x in xs if x is not None]
    return round(st.mean(xs), 3) if xs else None


def auswerten(pfade=None):
    """Erzeugt rq1_prompt_auswertung.csv und rq2_rag_auswertung.csv.

    Args:
        pfade: Liste von eval_rohdaten-CSV-Pfaden. None -> sucht persistence/csv/eval_rohdaten_*.csv.

    Aufrufbar aus test_neu.py (als Teil des Gesamtsystems) oder per CLI.
    """
    pfade = pfade or glob.glob("persistence/csv/eval_rohdaten_*.csv")
    if not pfade:
        print("  [Auswertung] Keine eval_rohdaten-CSV gefunden – uebersprungen.")
        return
    rows = lade(pfade)

    # (version, cid) -> {metrik: score}
    conv = defaultdict(dict)
    for r in rows:
        v = r.get("prompt_version", "")
        cid = r.get("conversation_id", "")
        s = r.get("score")
        if s not in (None, ""):
            try:
                conv[(v, cid)][kurz(r["metric"])] = float(s)
            except ValueError:
                pass

    # nach Version gruppieren
    per_version = defaultdict(list)   # version -> [scores_dict, ...]
    for (v, cid), sc in conv.items():
        per_version[v].append(sc)

    rq1 = [v for v in per_version if "__" not in v]
    rq2 = [v for v in per_version if "__" in v]

    # ---------- RQ1 ----------
    with open("rq1_prompt_auswertung.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        header = ["prompt_version", "n", "score_gewichtet", "gate_compliance_%"] + GEVAL_METRIKEN
        w.writerow(header)
        for v in sorted(rq1):
            gespr = per_version[v]
            weighted = [gewichteter_score(s) for s in gespr]
            gate = [gate_ok(s) for s in gespr]
            zeile = [v, len(gespr), mittel(weighted),
                     round(sum(gate) / len(gate) * 100) if gate else 0]
            for m in GEVAL_METRIKEN:
                zeile.append(mittel([s.get(m) for s in gespr]))
            w.writerow(zeile)
    print(f"RQ1 (Prompt-Effekt, GEval): {len(rq1)} Versionen -> rq1_prompt_auswertung.csv")

    # ---------- RQ2 ----------
    if rq2:
        with open("rq2_rag_auswertung.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["rag_konfiguration", "n"] + RAG_METRIKEN + ["score_gewichtet(sokratisch)"])
            for v in sorted(rq2):
                config = v.split("__", 1)[1]
                gespr = per_version[v]
                zeile = [config, len(gespr)]
                for m in RAG_METRIKEN:
                    zeile.append(mittel([s.get(m) for s in gespr]))
                zeile.append(mittel([gewichteter_score(s) for s in gespr]))
                w.writerow(zeile)
        print(f"RQ2 (RAG-Konfig, native): {len(rq2)} Konfigurationen -> rq2_rag_auswertung.csv")
    else:
        print("RQ2: keine Konfigurations-Laeufe gefunden (Versionsnamen ohne '__').")


if __name__ == "__main__":
    auswerten(sys.argv[1:] or None)