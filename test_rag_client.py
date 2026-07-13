# test_rag_client.py – Pilot-Lauf: Verbindungstest + Multi-Turn-Auswertung (Task #10-#12)
import json

from deepeval import evaluate
from deepeval.test_case import Turn, ConversationalTestCase
from deepeval.metrics import TurnRelevancyMetric

from rag_client import RAGPipelineClient
from clients import judge_llm
from config import THRESHOLD

client = RAGPipelineClient()  # nutzt RAG_BASE_URL/RAG_API_KEY/RAG_MODEL/RAG_VERIFY_SSL aus config.py

# =============================================================
# SCHRITT 1: Einzelcall gegen den echten Endpunkt (unverändert, Task #10)
# =============================================================
answer = client.ask(
    "Erklaere kurz den Unterschied zwischen Spannung und Strom.",
    collections="collection_labor, collection_vorlesung",
    retrieval="dense",
    is_cross_encoder_rerank=True,
)

print("=== ANTWORT ===")
print(answer.text)
print("\n=== QUELLEN (geparst) ===")
for c in answer.citations:
    print(c)
print("\n=== ROHE JSON-ANTWORT (zum Abgleich mit der Doku) ===")
print(json.dumps(answer.raw_response, indent=2, ensure_ascii=False))

# =============================================================
# SCHRITT 2: Pilot-Szenarien (Task #11)
# =============================================================
# TODO: durch eure eigenen 3-5 Pilot-Szenarien ersetzen/ergänzen.
# Turns sind bewusst fest verschriftet, nicht simuliert (Arbeitsanweisung Abschnitt 4 -
# sonst laufen die 7 Konfigurationen später in unterschiedliche Gespräche).
pilot_szenarien = [
    {
        "scenario_id": "spannung_strom_1",
        "turns": [
            {"query": "Was ist elektrische Spannung?"},
            {"query": "Und wie unterscheidet sich das von Strom?"},
            {"query": "Kannst du mir ein Alltagsbeispiel dafür geben?"},
        ],
    },
]


def build_conversation(scenario, **rag_config):
    """Spielt ein Szenario turn-für-turn gegen den RAG-Endpunkt ab und baut daraus
    ein ConversationalTestCase."""
    history, turns = [], []
    for step in scenario["turns"]:
        ans = client.ask(step["query"], history=history, **rag_config)
        history.append({"role": "user", "content": step["query"]})
        history.append({"role": "assistant", "content": ans.text})
        turns.append(Turn(role="user", content=step["query"]))
        turns.append(Turn(role="assistant", content=ans.text, retrieval_context=None))
    return ConversationalTestCase(
        turns=turns,
        chatbot_role="RAG-Tutor",
        expected_outcome=scenario.get("expected_outcome"),
    )


# =============================================================
# SCHRITT 3: Auswertung mit TurnRelevancyMetric (Task #12)
# =============================================================
print("\n=== MULTI-TURN-AUSWERTUNG (Dense, beide Collections, Rerank) ===")

test_cases = [
    build_conversation(
        s,
        collections="collection_labor, collection_vorlesung",
        retrieval="dense",
        is_cross_encoder_rerank=True,
    )
    for s in pilot_szenarien
]

metrics = [
    TurnRelevancyMetric(threshold=THRESHOLD, model=judge_llm, async_mode=False),
]

evaluate(test_cases=test_cases, metrics=metrics)