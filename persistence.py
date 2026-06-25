#persistence.py
import json
from deepeval.test_case import Turn, ConversationalTestCase
from config import CHATBOT_ROLE
# =============================================================
# KONVERSATIONEN SPEICHERN / LADEN
# =============================================================
 
def save_conversations(test_cases, metadata, filepath):
    """Speichert simulierte Konversationen als JSON."""
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
    """Lädt gespeicherte Konversationen aus JSON."""
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
 