# test_rag_smoke_verbose.py – Verbose-Smoke-Test fuer Pipeline v1.7.0
#
# Sendet einen einzelnen Request mit verbose=true (stream=false ist Pflicht) und
# parst die Verbose-JSON-Antwort. Zeigt vor allem, dass jetzt der CHUNK-TEXT
# verfuegbar ist (retrieval.final_chunks[].text) – der bisher fehlende
# retrieval_context (Task #13).
#
# WICHTIG (Doku v1.7.0, Abschnitt 6-8):
#   - verbose ist ein Top-Level-Requestparameter.
#   - stream MUSS false sein, sonst wird verbose ignoriert.
#   - choices[0].message.content ist dann ein JSON-STRING, kein Antworttext.
#   - Verbose legt System-Prompts, Chunks etc. offen -> nur fuer Eval/Dev.
#
# Ausfuehren mit: python test_rag_smoke_verbose.py

import json
import requests
import urllib3

from config import OPENWEBUI_BASE_URL, OPENWEBUI_API_KEY, RAG_MODEL, RAG_VERIFY_SSL

if not RAG_VERIFY_SSL:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

payload = {
    "model": RAG_MODEL,
    "stream": False,          # Pflicht fuer verbose
    "verbose": True,          # <-- schaltet die Verbose-Transparenz ein
    "collections": "hollstein_collection_labor, hollstein_collection_vorlesung",
    "retrieval": "dense",
    "is_cross_encoder_rerank": False,
    "messages": [
        {"role": "user", "content": "Was ist eine Z-Diode"}
    ],
}

resp = requests.post(
    f"{OPENWEBUI_BASE_URL.rstrip('/')}",
    headers={"Authorization": f"Bearer {OPENWEBUI_API_KEY}", "Content-Type": "application/json"},
    json=payload,
    timeout=300,
    verify=RAG_VERIFY_SSL,
)
resp.raise_for_status()

outer = resp.json()
content = outer["choices"][0]["message"]["content"]

# Bei verbose=true ist content ein JSON-STRING -> parsen.
try:
    v = json.loads(content)
except (json.JSONDecodeError, TypeError):
    print("!! content ist KEIN Verbose-JSON. Ist verbose=true angekommen und stream=false?")
    print(content)
    raise SystemExit(1)

print("verbose_effective:", (v.get("request") or {}).get("verbose_effective"))

print("\n=== FINALE ANTWORT (final_answer) ===")
print(v.get("final_answer", ""))

retrieval = v.get("retrieval") or {}
final_chunks = retrieval.get("final_chunks") or []
print(f"\n=== FINALE RETRIEVAL-CHUNKS (mit TEXT): {len(final_chunks)} ===")
for c in final_chunks:
    print(f"\n[rank {c.get('rank')}] collection={c.get('collection')} "
          f"score={c.get('score')} page={c.get('page')} chunk_index={c.get('chunk_index')}")
    print("  source:", c.get("source") or c.get("title"))
    text = (c.get("text") or "").strip()
    print("  text:", (text[:300] + " ...") if len(text) > 300 else text)

# ---- ECHTER retrieval_context (genau so, wie ihn DeepEval bekommt) ----
retrieval_context = [c["text"] for c in final_chunks if (c.get("text") or "").strip()]
print(f"\n=== retrieval_context (fuer DeepEval): {len(retrieval_context)} Chunks ===")
for i, txt in enumerate(retrieval_context, start=1):
    print(f"\n--- Chunk {i} ---")
    print(txt)

sources = (v.get("pipeline_addendum") or {}).get("sources") or []
print(f"\n=== SICHTBARE QUELLEN (pipeline_addendum.sources): {len(sources)} ===")
for s in sources:
    print(f"  - {s.get('visible_title') or s.get('title')} | {s.get('url')} "
          f"| page={s.get('page')} | score={s.get('score')} | collection={s.get('collection')}")

# Vollstaendige Struktur zum Nachschlagen:
with open("verbose_dump.json", "w", encoding="utf-8") as f:
    json.dump(v, f, ensure_ascii=False, indent=2)
print("\nVollstaendige Verbose-Antwort gespeichert -> verbose_dump.json")