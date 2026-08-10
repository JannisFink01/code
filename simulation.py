# simulation.py
"""Simuliert die Gespraeche fuer eine Prompt-Version gegen den RAG-Endpunkt
(System unter Test) und speichert sie ABSTURZSICHER und RESUME-FAEHIG.

Design:
- Weg 2: Waehrend der Simulation gibt der Callback SCHLANKE Turns zurueck (nur
  role+content), damit der grosse Verbose-retrieval_context nicht in den
  Simulator-Prompt gelangt. Kontext + Metadaten werden separat gesammelt und
  ERST NACH der Simulation eines Gespraechs an dessen Assistant-Turns gehaengt.
- Pro Gespraech (nicht am Ende) wird die Konversations-JSON atomar neu geschrieben
  (Temp-Datei + os.replace). Ein Absturz kostet damit hoechstens das gerade
  laufende Gespraech; beim Neustart werden bereits vorhandene conversation_ids
  uebersprungen (Resume).
"""
import os
import hashlib
from datetime import timezone, datetime

from deepeval.test_case import Turn
from deepeval.dataset import ConversationalGolden
from deepeval.simulator import ConversationSimulator

from config import (
    RAG_CONFIG,
    BASE_WAIT,
    CAP,
    REPEATS,
    MAX_USER_SIMULATIONS,
    CHATBOT_ROLE,
    MAX_RETRIES,
    conv_path,
)
from clients import rate_limiter, simulator_llm, rag_llm
from retry_utils import retry_async
from scenarios import build_scenarios
from persistence import save_conversations, load_conversations

# None = alle Szenarien simulieren; z. B. 5 = nur 5 Gespraeche (Pilot).
MAX_CONVERSATIONS = None


def make_conversation_id(version, topic, level, behavior, repeat):
    """Erzeugt eine stabile, kurze ID fuer ein Gespraech aus seinen Szenario-Feldern."""
    raw = f"{version}|{topic}|{level}|{behavior}|{repeat}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]


def _speichern_atomar(test_cases, metadata, c_path):
    """Schreibt die Konversationen atomar: erst in eine Temp-Datei, dann umbenennen.

    Ein Absturz mitten im Schreiben laesst so die bisherige (vollstaendige) Datei
    unversehrt, statt eine halb geschriebene JSON zu hinterlassen.
    """
    os.makedirs(os.path.dirname(c_path), exist_ok=True)
    tmp = c_path + ".tmp"
    save_conversations(test_cases, metadata, tmp)
    os.replace(tmp, c_path)


def simulate_conversations(prompt_file: str, version: str):
    """Simuliert alle Konversationen fuer eine Prompt-Version, resume-faehig.

    Args:
        prompt_file: Pfad zur System-Prompt-Datei.
        version: Kurzname der Prompt-Version (bestimmt den Cache-Pfad).

    Returns:
        Tupel (test_cases, metadata) – alle (auch zuvor schon gespeicherten)
        Gespraeche und die zugehoerigen Szenario-Metadaten (index-gleich).
    """
    with open(prompt_file, encoding="utf-8") as f:
        system_prompt = f.read()

    c_path = conv_path(version)

    # =========================================================
    # SZENARIEN / GOLDENS AUFBAUEN (immer die volle Sollmenge)
    # =========================================================
    scenarios = build_scenarios()
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
                        f"Studierende:r ({s['level']}), Verhalten: {s['behavior']}."
                    ),
                    expected_outcome="Die studierende Person kommt durch sokratische Rueckfragen selbst auf die Erklaerung; die Loesung wird nie direkt verraten.",
                    user_description=f"{s['level']}-Studierende:r der Elektrotechnik. Verhalten: {s['behavior']}. Antworte auf Deutsch.",
                    # feste Startfrage (wortgleich) – der Simulator uebernimmt sie als 1. Turn
                    turns=[Turn(role="user", content=s["initial_question"])],
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

    # =========================================================
    # RESUME: bereits gespeicherte Gespraeche laden und ueberspringen
    # =========================================================
    all_test_cases, all_metadata = [], []
    done_ids = set()
    if os.path.exists(c_path):
        all_test_cases, all_metadata = load_conversations(c_path)
        done_ids = {m.get("conversation_id") for m in all_metadata}
        print(f"  {len(done_ids)} Gespraeche bereits vorhanden -> Resume")

    pending = [
        (g, m) for g, m in zip(goldens, metadata)
        if m["conversation_id"] not in done_ids
    ]
    if not pending:
        print(f"  Alle {len(goldens)} Gespraeche bereits simuliert -> nichts zu tun")
        return all_test_cases, all_metadata

    print(f"  {len(pending)} von {len(goldens)} Gespraechen simulieren...")

    # Weg 2: Kontext/Metadaten separat sammeln (nach Antworttext), spaeter an Turns haengen.
    kontext_je_antwort = {}
    meta_je_antwort = {}

    async def prompt_callback(
        input: str, turns: list[Turn] = None, thread_id: str = None
    ) -> Turn:
        """Callback: naechste Antwort vom RAG-Endpunkt. Gibt einen SCHLANKEN Turn
        zurueck (nur role+content), damit der grosse Kontext nicht in den
        Simulator-Prompt gelangt."""
        history = [{"role": t.role, "content": t.content} for t in (turns or [])]

        async def _do():
            await rate_limiter.a_acquire()
            resp = rag_llm.ask(
                input,
                system_prompt=system_prompt,
                history=history,
                verbose=True,               # echter retrieval_context aus Verbose
                **RAG_CONFIG,
            )
            kontext_je_antwort[resp.text] = resp.retrieval_context
            meta_je_antwort[resp.text] = {
                "studenten_frage": input,
                "quellen": [c.__dict__ for c in resp.citations],
                "rohe_json_antwort": resp.raw_response,
                "rag_config": RAG_CONFIG,
            }
            return Turn(role="assistant", content=resp.text)

        return await retry_async(
            _do,
            max_retries=MAX_RETRIES,
            base_wait=BASE_WAIT,
            cap=CAP,
            label="RAG",
        )

    simulator = ConversationSimulator(
        model_callback=prompt_callback, simulator_model=simulator_llm
    )

    # =========================================================
    # PRO GESPRAECH simulieren, Kontext anhaengen, atomar speichern
    # =========================================================
    for i, (golden, meta) in enumerate(pending, start=1):
        cid = meta["conversation_id"]
        print(f"  [{i}/{len(pending)}] simuliere {cid} | {meta.get('topic','?')[:40]}")
        try:
            tcs = simulator.simulate(
                conversational_goldens=[golden],
                max_user_simulations=MAX_USER_SIMULATIONS,
            )
        except Exception as e:
            # Ein fehlgeschlagenes Gespraech NICHT speichern -> bleibt pending,
            # naechster Lauf versucht es erneut. Der Rest laeuft weiter.
            print(f"    ⚠ {cid} uebersprungen ({type(e).__name__}: {e})")
            continue

        tc = tcs[0]
        tc.chatbot_role = CHATBOT_ROLE
        for turn in tc.turns:
            if turn.role == "assistant":
                turn.retrieval_context = kontext_je_antwort.get(turn.content)
                turn.metadata = {"rag_metadata": meta_je_antwort.get(turn.content)}

        all_test_cases.append(tc)
        all_metadata.append(meta)
        _speichern_atomar(all_test_cases, all_metadata, c_path)
        print(f"    ✓ gespeichert ({len(all_metadata)}/{len(goldens)})")

    print(f"  Fertig -> {c_path}")
    return all_test_cases, all_metadata