# evaluation.py
import os
import time
import csv
import asyncio
from collections import defaultdict
from deepeval import evaluate
from deepeval.test_case import Turn
from deepeval.dataset import ConversationalGolden
from deepeval.simulator import ConversationSimulator
from config import (
    TUTOR_MODEL,
    REPEATS,
    MAX_USER_SIMULATIONS,
    CHATBOT_ROLE,
)
from clients import rate_limiter, judge_llm, simulator_llm, tutor_llm, CONTEXT
from scenarios import build_scenarios
from metrics import build_metrics
from persistence import save_conversations, load_conversations

EVAL_MAX_RETRIES = 5
EVAL_RETRY_WAIT = 45


def run_evaluation(prompt_file: str, version: str):

    with open(prompt_file, encoding="utf-8") as f:
        system_prompt = f.read()

    print(f"\n{'='*60}")
    print(f"  Starte Evaluation: {version} ({prompt_file})")
    print(f"{'='*60}")

    conv_path = f"konversationen_{version}.json"
    raw_path = f"eval_rohdaten_{version}.csv"
    agg_path = f"eval_aggregat_{version}.csv"
    fieldnames = ["prompt_version", "topic", "level", "behavior",
                  "repeat", "metric", "score", "success", "reason"]

    # =========================================================
    # SIMULATION (oder aus Cache laden)
    # =========================================================
    if os.path.exists(conv_path):
        print(f"  Konversationen existieren → überspringe Simulation")
        test_cases, metadata = load_conversations(conv_path)

    else:
        scenarios = build_scenarios()
        goldens, metadata = [], []

        for s in scenarios:
            for rep in range(REPEATS):
                goldens.append(ConversationalGolden(
                    scenario=f"Thema: {s['topic']}. Studierende:r ({s['level']}), Verhalten: {s['behavior']}.",
                    expected_outcome="Die studierende Person kommt durch sokratische Rückfragen selbst auf die Erklärung; die Lösung wird nie direkt verraten.",
                    user_description=f"{s['level']}-Studierende:r der Elektrotechnik. Verhalten: {s['behavior']}.",
                ))
                metadata.append({**s, "repeat": rep + 1})

        print(f"  {len(goldens)} Konversationen simulieren...")

        # --- Tutor Callback (innerhalb else) ---
        async def prompt_callback(input: str, turns: list[Turn] = None, thread_id: str = None) -> Turn:
            messages = [{"role": "system", "content": system_prompt}]
            for t in turns or []:
                messages.append({"role": t.role, "content": t.content})
            messages.append({"role": "user", "content": input})
            for attempt in range(1, EVAL_MAX_RETRIES + 1):
                try:
                    await rate_limiter.a_acquire()
                    resp = tutor_llm._client.chat.completions.create(
                        model=TUTOR_MODEL, messages=messages,
                        extra_body={"enable_thinking": False},
                    )
                    return Turn(role="assistant", content=resp.choices[0].message.content,
                                retrieval_context=[system_prompt, CONTEXT])
                except Exception as e:
                    if attempt < EVAL_MAX_RETRIES:
                        wait = min(45 * attempt, 180)
                        print(f"    ⟳ Tutor Retry {attempt}/{EVAL_MAX_RETRIES} ({type(e).__name__}) – warte {wait}s")
                        await asyncio.sleep(wait)
                    else:
                        raise

        # --- Simulator (innerhalb else) ---
        simulator = ConversationSimulator(model_callback=prompt_callback, simulator_model=simulator_llm)
        test_cases = simulator.simulate(conversational_goldens=goldens, max_user_simulations=MAX_USER_SIMULATIONS)
        for tc in test_cases:
            tc.chatbot_role = CHATBOT_ROLE
        save_conversations(test_cases, metadata, conv_path)

    # =========================================================
    # RESUME-CHECK: bereits evaluierte Testfälle ermitteln
    # =========================================================
    already_done = set()
    if os.path.exists(raw_path):
        with open(raw_path, "r", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                key = (row.get("topic", ""), row.get("behavior", ""), row.get("repeat", ""))
                already_done.add(key)
        # Anzahl unique Testfälle (jeder hat mehrere Metrik-Zeilen)
        print(f"  {len(already_done)} Testfälle bereits evaluiert – setze fort.")
    else:
        with open(raw_path, "w", newline="", encoding="utf-8-sig") as f:
            csv.DictWriter(f, fieldnames=fieldnames).writeheader()

    # =========================================================
    # EVALUATION (sequenziell, mit Resume + Retry)
    # =========================================================
    print(f"\n  {len(test_cases)} Testfälle evaluieren...")
    metrics = build_metrics(judge_llm)

    rows = []
    skipped = 0
    for i, tc in enumerate(test_cases):
        meta = metadata[i] if i < len(metadata) else {}
        key = (meta.get("topic", ""), meta.get("behavior", ""), str(meta.get("repeat", "")))

        # Bereits evaluiert → überspringen
        if key in already_done:
            skipped += 1
            continue

        print(f"  [{i+1}/{len(test_cases)}] {meta.get('topic','?')[:35]} | {meta.get('behavior','?')[:25]}")

        for metric in metrics:
            metric_name = getattr(metric, "__name__", "?")
            for attempt in range(1, EVAL_MAX_RETRIES + 1):
                try:
                    metric.measure(tc)
                    row = {
                        "prompt_version": version,
                        "topic": meta.get("topic", ""), "level": meta.get("level", ""),
                        "behavior": meta.get("behavior", ""), "repeat": meta.get("repeat", ""),
                        "metric": metric_name, "score": metric.score,
                        "success": metric.score >= metric.threshold if metric.score is not None else None,
                        "reason": (metric.reason or "").replace("\n", " "),
                    }
                    rows.append(row)
                    with open(raw_path, "a", newline="", encoding="utf-8-sig") as f:
                        csv.DictWriter(f, fieldnames=fieldnames).writerow(row)
                    break
                except Exception as e:
                    if attempt < EVAL_MAX_RETRIES:
                        wait = min(EVAL_RETRY_WAIT * attempt, 180)
                        print(f"    ⟳ {metric_name} Retry {attempt}/{EVAL_MAX_RETRIES} – warte {wait}s")
                        time.sleep(wait)
                    else:
                        print(f"    ⚠ {metric_name} übersprungen")

        print(f"    ✓ fertig")

    evaluated = len(test_cases) - skipped
    print(f"\n  {evaluated} neu evaluiert | {skipped} übersprungen")

    # =========================================================
    # AGGREGAT
    # =========================================================
    all_rows = []
    with open(raw_path, "r", encoding="utf-8-sig") as f:
        all_rows = list(csv.DictReader(f))

    agg = defaultdict(list)
    for r in all_rows:
        score = r.get("score")
        if score is not None and score != "":
            agg[(r["behavior"], r["metric"])].append((float(score), r.get("success") == "True"))

    with open(agg_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["behavior", "metric", "avg_score", "pass_rate", "n"])
        for (behavior, metric), vals in sorted(agg.items()):
            scores = [v[0] for v in vals]
            passes = [1 for v in vals if v[1]]
            w.writerow([behavior, metric, round(sum(scores)/len(scores), 3),
                        round(len(passes)/len(vals), 3), len(vals)])

    print(f"\n  Rohdaten → {raw_path}")
    print(f"  Aggregat → {agg_path}")