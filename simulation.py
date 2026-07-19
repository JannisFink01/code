# simulation.py
"""Orchestriert einen kompletten Evaluierungslauf für eine Prompt-Version: simulieren
(oder aus Cache laden), pro Konversation alle Metriken berechnen (mit Resume + Retry)
und die Ergebnisse als Rohdaten- sowie Aggregat-CSV ablegen."""

from datetime import timezone, datetime
import json
import json
import os
import hashlib
from retry_utils import retry_sync
from collections import defaultdict
from deepeval.test_case import Turn
from deepeval.dataset import ConversationalGolden
from deepeval.simulator import ConversationSimulator
from config import (
    RAG_CONFIG,
    BASE_WAIT,
    CAP,
    FIELDNAMES,
    TUTOR_MODEL,
    REPEATS,
    MAX_USER_SIMULATIONS,
    CHATBOT_ROLE,
    conv_path,
    agg_path,
    raw_path,
    MAX_RETRIES,
)
from clients import rate_limiter, judge_llm, simulator_llm, tutor_llm, rag_llm, CONTEXT
from retry_utils import retry_async
from scenarios import build_scenarios, build_pilot_scenarios
from persistence import save_conversations, load_conversations

MAX_CONVERSATIONS = 5

rag_config = RAG_CONFIG
# =========================================================
# SIMULATION (oder aus Cache laden)
# =========================================================


def make_conversation_id(version, topic, level, behavior, repeat):
    """Erzeugt eine stabile, kurze ID fuer ein Gespraech aus seinen Szenario-Feldern."""
    raw = f"{version}|{topic}|{level}|{behavior}|{repeat}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]


def simulate_conversations(prompt_file: str, version: str):
    """Simuliert alle Konversationen für eine Prompt-Version (oder lädt sie aus Cache).

    Args:
        prompt_file: Pfad zur System-Prompt-Datei.
        version: Kurzname der Prompt-Version (bestimmt den Cache-Pfad).

    Returns:
        Tupel (test_cases, metadata) – die simulierten/geladenen Gespraeche und
        die zugehoerigen Szenario-Metadaten (index-gleich).
    """
    with open(prompt_file, encoding="utf-8") as f:
        system_prompt = f.read()

    c_path = conv_path(version)
    print(f"  Prüfe, ob Konversationen bereits existieren: {c_path}")

    # --- Doppel-Simulations-Schutz: existiert der Cache, wird nicht neu simuliert ---
    if os.path.exists(c_path):
        print(f"  Konversationen existieren → überspringe Simulation")
        test_cases, metadata = load_conversations(c_path)
        return test_cases, metadata

    # =========================================================
    # SZENARIEN / GOLDENS AUFBAUEN
    # =========================================================
    scenarios = build_pilot_scenarios()
    goldens, metadata = [], []
    prompt_hash = hashlib.sha1(system_prompt.encode("utf-8")).hexdigest()[:10]
    run_started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    for s in scenarios:
        for rep in range(REPEATS):
            cid = make_conversation_id(
                version, s["topic"], s["level"], s["behavior"], rep + 1
            )
            goldens.append(
                ConversationalGolden(
                    scenario=(
                        f"Thema: {s['topic']}. "
                        f"Studierende:r ({s['level']}), Verhalten: {s['behavior']}. "
                        f"Die erste Frage des Studierenden lautet exakt: \"{s['initial_question']}\""
                    ),
                    expected_outcome="Die studierende Person kommt durch sokratische Rückfragen selbst auf die Erklärung; die Lösung wird nie direkt verraten.",
                    user_description=f"{s['level']}-Studierende:r der Elektrotechnik. Verhalten: {s['behavior']}. Antworte auf Deutsch.",
                )
            )
            metadata.append(
                {
                    **s,
                    "repeat": rep + 1,
                    "conversation_id": cid,
                    "prompt_version": version,
                    "prompt_hash": prompt_hash,
                    "run_started_at": run_started_at,
                }
            )
    if MAX_CONVERSATIONS is not None:
        goldens = goldens[:MAX_CONVERSATIONS]
        metadata = metadata[:MAX_CONVERSATIONS]

        print(f"  {len(goldens)} Konversationen simulieren...")
    rag_metadaten_log = []

    # =========================================================
    # RAG-CALLBACK (ersetzt das fruehere Tutor-LLM)
    # =========================================================
    async def prompt_callback(
        input: str, turns: list[Turn] = None, thread_id: str = None
    ) -> Turn:
        """Callback für den ConversationSimulator: erzeugt die nächste RAG-Antwort.

        Baut aus System-Prompt und bisherigem Verlauf (`turns`) die Chat-Nachrichten,
        ruft das RAG-Modell auf (mit Rate Limiting und Retry) und gibt die Antwort
        als `Turn` samt Retrieval-Kontext (System-Prompt + Fachkontext) zurück.

        Args:
            input: Die aktuelle Nachricht des simulierten Studierenden.
            turns: Bisheriger Gesprächsverlauf (ohne System-Nachricht).
            thread_id: Von DeepEval übergebene Konversations-ID (hier ungenutzt).

        Returns:
            Der neue `Turn` mit der RAG-Antwort.
        """
        history = [{"role": t.role, "content": t.content} for t in (turns or [])]

        async def _do():
            await rate_limiter.a_acquire()
            resp = rag_llm.ask(
                input,
                system_prompt=system_prompt,
                history=history,
                **RAG_CONFIG,
            )
            rag_metadaten_log.append(
                {
                    "thread_id": thread_id,
                    "turn_index": len(history),
                    "studenten_frage": input,
                    "rag_antwort": resp.text,
                    "quellen": [c.__dict__ for c in resp.citations],
                    "rohe_json_antwort": resp.raw_response,
                    "rag_config": RAG_CONFIG,
                }
            )
            return Turn(
                role="assistant",
                content=resp.text,
                retrieval_context=[c.raw for c in resp.retrieval_context] or None,
            )

        return await retry_async(
            _do,
            max_retries=MAX_RETRIES,
            base_wait=BASE_WAIT,
            cap=CAP,
            label="RAG",
        )

    # =========================================================
    # SIMULATION AUSFUEHREN
    # =========================================================
    simulator = ConversationSimulator(
        model_callback=prompt_callback, simulator_model=simulator_llm
    )
    test_cases = simulator.simulate(
        conversational_goldens=goldens, max_user_simulations=MAX_USER_SIMULATIONS
    )
    for tc in test_cases:
        tc.chatbot_role = CHATBOT_ROLE

    save_conversations(test_cases, metadata, c_path)
    print(f"  Konversationen gespeichert -> {c_path}")
    rag_log_path = c_path.replace(".json", "_rag_metadaten.json")
    with open(rag_log_path, "w", encoding="utf-8") as f:
        json.dump(rag_metadaten_log, f, ensure_ascii=False, indent=2)
    print(f"  RAG-Metadaten gespeichert -> {rag_log_path}")
 
    return test_cases, metadata    
