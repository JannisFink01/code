# evaluation.py
from datetime import timezone, datetime
import os
import hashlib
import csv
from retry_utils import retry_sync
from collections import defaultdict
from deepeval.test_case import Turn
from deepeval.dataset import ConversationalGolden
from deepeval.simulator import ConversationSimulator
from config import (
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
from clients import rate_limiter, judge_llm, simulator_llm, tutor_llm, CONTEXT
from retry_utils import retry_async
from scenarios import build_scenarios
from metrics import build_metrics
from persistence import attach_results, save_conversations, load_conversations


def make_conversation_id(version, topic, level, behavior, repeat):
    raw = f"{version}|{topic}|{level}|{behavior}|{repeat}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]


def _evaluate_single(tc, metrics, meta, version):
    results = []
    for metric in metrics:
        metric_name = getattr(metric, "__name__", "?")
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
                    "prompt_version": version,
                    "topic": meta.get("topic", ""),
                    "level": meta.get("level", ""),
                    "behavior": meta.get("behavior", ""),
                    "repeat": meta.get("repeat", ""),
                    "metric": metric_name,
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
                    "prompt_version": version,
                    "topic": meta.get("topic", ""),
                    "level": meta.get("level", ""),
                    "behavior": meta.get("behavior", ""),
                    "repeat": meta.get("repeat", ""),
                    "metric": metric_name,
                    "score": None,
                    "success": None,
                    "reason": f"ERROR: {type(e).__name__}: {e}",
                    "verbose_logs": getattr(metric, "verbose_logs", None),
                }
            )
    return results


def run_evaluation(prompt_file: str, version: str):

    with open(prompt_file, encoding="utf-8") as f:
        system_prompt = f.read()

    print(f"\n{'='*60}")
    print(f"  Starte Evaluation: {version} ({prompt_file})")
    print(f"{'='*60}")
    r_path = raw_path(version)
    a_path = agg_path(version)
    c_path = conv_path(version)
    # =========================================================
    # SIMULATION (oder aus Cache laden)
    # =========================================================
    print(f"  Prüfe, ob Konversationen bereits existieren: {c_path}")
    if os.path.exists(c_path):
        print(f"  Konversationen existieren → überspringe Simulation")
        test_cases, metadata = load_conversations(c_path)

    else:
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

        print(f"  {len(goldens)} Konversationen simulieren...")

        # --- Tutor Callback (innerhalb else) ---
        async def prompt_callback(
            input: str, turns: list[Turn] = None, thread_id: str = None
        ) -> Turn:
            messages = [{"role": "system", "content": system_prompt}]
            for t in turns or []:
                messages.append({"role": t.role, "content": t.content})
            messages.append({"role": "user", "content": input})

            async def _do():
                await rate_limiter.a_acquire()
                resp = tutor_llm._client.chat.completions.create(
                    model=TUTOR_MODEL,
                    messages=messages,
                    extra_body={"enable_thinking": False},
                )
                return Turn(
                    role="assistant",
                    content=resp.choices[0].message.content,
                    retrieval_context=[system_prompt, CONTEXT],
                )

            return await retry_async(
                _do,
                max_retries=MAX_RETRIES,
                base_wait=BASE_WAIT,
                cap=CAP,
                label="Tutor",
            )

        # --- Simulator (innerhalb else) ---
        simulator = ConversationSimulator(
            model_callback=prompt_callback, simulator_model=simulator_llm
        )
        test_cases = simulator.simulate(
            conversational_goldens=goldens, max_user_simulations=MAX_USER_SIMULATIONS
        )
        for tc in test_cases:
            tc.chatbot_role = CHATBOT_ROLE
        save_conversations(test_cases, metadata, c_path)

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
        # Anzahl unique Testfälle (jeder hat mehrere Metrik-Zeilen)
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
    by_id = defaultdict(list)
    for r in all_rows:
        if r.get("conversation_id"):
            by_id[r["conversation_id"]].append(r)
    attach_results(c_path, by_id)
