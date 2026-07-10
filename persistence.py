#persistence.py
"""Speichert und lädt simulierte Konversationen (ConversationalTestCase + Metadaten) als JSON,
damit eine einmal simulierte Konversation nicht bei jedem Skript-Neustart neu erzeugt werden muss."""
import json
from deepeval.test_case import Turn, ConversationalTestCase
from config import CHATBOT_ROLE
# =============================================================
# KONVERSATIONEN SPEICHERN / LADEN
# =============================================================
 
def save_conversations(test_cases, metadata, filepath):
    """Speichert simulierte Konversationen als JSON-Datei.
 
    Args:
        test_cases: Liste von `ConversationalTestCase`-Objekten (z. B. Rückgabe von
            `ConversationSimulator.simulate(...)`).
        metadata: Liste von Dicts mit Szenario-Infos (topic/level/behavior/repeat/...),
            an derselben Position wie das zugehörige Element in `test_cases`.
        filepath: Zielpfad der JSON-Datei (siehe `config.conv_path`).
    """
    data = []
    for i, tc in enumerate(test_cases):
        meta = metadata[i] if i < len(metadata) else {}
        turns = []
        for t in tc.turns:
            turns.append({
                "role": t.role,
                "content": t.content,
                "retrieval_context": getattr(t, "retrieval_context", None),
            })
        data.append({"meta": meta, "turns": turns, "chatbot_role": tc.chatbot_role})
 
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  Konversationen gespeichert → {filepath}")
 
 
def load_conversations(filepath):
    """Lädt zuvor gespeicherte Konversationen aus einer JSON-Datei.
 
    Args:
        filepath: Pfad der JSON-Datei, wie sie von `save_conversations` geschrieben wurde.
 
    Returns:
        Tupel `(test_cases, metadata)`:
            test_cases: Liste rekonstruierter `ConversationalTestCase`-Objekte.
            metadata: Liste der zugehörigen Szenario-Infos, gleiche Reihenfolge wie test_cases.
    """    
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
 
    test_cases, metadata = [], []
    for item in data:
        turns = []
        for t in item["turns"]:
            turns.append(Turn(
                role=t["role"],
                content=t["content"],
                retrieval_context=t.get("retrieval_context"),
            ))
        tc = ConversationalTestCase(turns=turns, chatbot_role=item.get("chatbot_role", CHATBOT_ROLE))
        test_cases.append(tc)
        metadata.append(item["meta"])
 
    print(f"  Konversationen geladen ← {filepath} ({len(test_cases)} Testfälle)")
    return test_cases, metadata

def attach_results(filepath, results_by_id):
    """Reichert eine bereits gespeicherte Konversationsdatei um die Metrik-Ergebnisse an."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    for item in data:
        cid = item["meta"].get("conversation_id")
        item["results"] = results_by_id.get(cid, [])
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  Scores in Konversationsdatei geschrieben → {filepath}")