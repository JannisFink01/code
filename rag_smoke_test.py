# test_rag_smoke.py – Minimal-Test: zeigt nur, dass der Code den RAG-Endpunkt
# erfolgreich anspricht und eine Antwort zurueckkommt. Keine Metriken, keine
# Szenarien, kein DeepEval - nur ein einziger Request.
#
# Ausfuehren mit: python test_rag_smoke.py

from rag_client import RAGPipelineClient

client = RAGPipelineClient()

answer = client.ask(
    "Wie ist der Aufbau einer Stabilisierungsschaltung.",
    collections="hollstein_collection_labor, hollstein_collection_vorlesung",
    retrieval="dense",
    is_cross_encoder_rerank=True,
)

print("=== ANTWORT ===")
print(answer.text)

print("\n=== QUELLEN ===")
print(answer.citations)
for c in answer.citations:
    print(c)