from dotenv import load_dotenv
import os
from collections import defaultdict
import csv
from openai import OpenAI
from deepeval import evaluate
from deepeval.test_case import Turn, MultiTurnParams
from deepeval.dataset import ConversationalGolden
from deepeval.simulator import ConversationSimulator
from deepeval.metrics import (
    ConversationalGEval,
    ConversationCompletenessMetric,
    RoleAdherenceMetric,
)

try:
    from deepeval.metrics import ConversationRelevancyMetric as RelevancyMetric
except ImportError:
    from deepeval.metrics import TurnRelevancyMetric as RelevancyMetric

load_dotenv()
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
TUTOR_MODEL = os.getenv("TUTOR_MODEL", "gemma-4-31b-it")      # das ZU TESTENDE Modell
SIMULATOR_MODEL = os.getenv("SIMULATOR_MODEL", "meta-llama-3.1-8b-instruct")  # Student
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "openai-gpt-oss-120b")
REPEATS = 3                  # Wiederholungen pro Szenario
MAX_USER_SIMULATIONS = 6     # Frage-Antwort-Runden pro Gespraech
THRESHOLD = 0.7
PROMPT_VERSION = os.getenv("PROMPT_VERSION", "v1")

CHATBOT_ROLE = "Sokrat: ein sokratischer Tutor, der mit Rückfragen führt und die Lösung nie direkt verrät."
 
with open("system_prompt.txt", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()

client = OpenAI(api_key=os.getenv("GWDG_API_KEY"), base_url=os.getenv("GWDG_BASE_URL"));

TOPICS = [
    "Sperrspannung und Durchbruch bei der Z-Diode",
    "Spannungsstabilisierung mit Vorwiderstand und Z-Diode",
    "Ohmsches Gesetz und Maschenregel",
]
LEVELS = ["Anfänger", "Fortgeschritten"]

BEHAVIORS = [
    "kooperativ und denkt mit",
    "gibt schnell auf und sagt 'ich weiß es nicht'",
    "fordert direkt die Lösung ein ('sag mir einfach die Antwort')",
    "schlägt eine Vermutung vor und fragt 'stimmt das?'",
    "ist selbstsicher, aber inhaltlich falsch",
]
 
 
def build_scenarios():
    scenarios = []
    for topic in TOPICS:
        for behavior in BEHAVIORS:
            scenarios.append({"topic": topic, "level": "Anfänger", "behavior": behavior})
    for topic in TOPICS:
        for behavior in BEHAVIORS[2:]:
            scenarios.append({"topic": topic, "level": "Fortgeschritten", "behavior": behavior})
    return scenarios
 


async def model_callback(input: str, turns: list[Turn] = None, thread_id: str = None) -> Turn:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for t in (turns or []):
        messages.append({"role": t.role, "content": t.content})
    messages.append({"role": "user", "content": input})

    resp = client.chat.completions.create(model=TUTOR_MODEL, messages=messages)
    return Turn(role="assistant", content=resp.choices[0].message.content)
def build_metrics():
    params = [MultiTurnParams.CONTENT]
    keine_loesung = ConversationalGEval(
        name="Keine Lösung verraten",
        evaluation_steps=[
            "Pruefe, ob der Tutor die Loesung/das Ergebnis direkt oder als Bestaetigung einer Vermutung preisgibt.",
            "Bestrafe das Verraten der Loesung sehr stark, auch unter Druck (Aufforderung, Aufgeben, 'Zeit ist um').",
            "Das blosse Eingrenzen oder Bestaetigen eines DENKSCHRITTS (nicht der Endloesung) ist erlaubt.",
        ],
        evaluation_params=params, model=JUDGE_MODEL, threshold=THRESHOLD,
    )
    gegenfragen = ConversationalGEval(
        name="Stellt Gegenfragen",
        evaluation_steps=[
            "   Pruefe, ob der Tutor ueberwiegend mit leitenden Fragen antwortet statt zu dozieren.",
            "Belohne offene Fragen, die zum Nachdenken anregen und an die letzte Antwort anknuepfen.",
            "Bestrafe rein erklaerende Antworten ohne Rueckfrage.",
        ],
        evaluation_params=params, model=JUDGE_MODEL, threshold=THRESHOLD,
    )
    schrittweise = ConversationalGEval(
        name="Führt schrittweise",
        evaluation_steps=[
            "Pruefe, ob das Problem in kleine, aufeinander aufbauende Schritte zerlegt wird.",
            "Belohne das Absichern eines Schritts, bevor zum naechsten uebergegangen wird.",
            "Bestrafe Spruenge ueber mehrere Konzepte ohne Zwischenschritte.",
        ],
        evaluation_params=params, model=JUDGE_MODEL, threshold=THRESHOLD,
    )
    niveau = ConversationalGEval(
        name="Passt Niveau an",
        evaluation_steps=[
            "Pruefe, ob Sprache und Komplexitaet zum erkennbaren Niveau der studierenden Person passen.",
            "Belohne einfachere Erklaerungen/Beispiele als Reaktion auf Verwirrung.",
            "Bestrafe unangepasste Fachsprache trotz klarer Signale.",
        ],
        evaluation_params=params, model=JUDGE_MODEL, threshold=THRESHOLD,
    )
    native = [
        RelevancyMetric(threshold=THRESHOLD, model=JUDGE_MODEL),
        ConversationCompletenessMetric(threshold=THRESHOLD, model=JUDGE_MODEL),
        RoleAdherenceMetric(threshold=THRESHOLD, model=JUDGE_MODEL),
    ]
    return [keine_loesung, gegenfragen, schrittweise, niveau] + native

def main():
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
 
    print(f"{len(goldens)} Konversationen werden simuliert "
          f"({len(scenarios)} Szenarien x {REPEATS} Wiederholungen)...")
 
    simulator = ConversationSimulator(model_callback=model_callback, simulator_model=SIMULATOR_MODEL)
    test_cases = simulator.simulate(conversational_goldens=goldens,
                                    max_user_simulations=MAX_USER_SIMULATIONS)
    for tc in test_cases:
        tc.chatbot_role = CHATBOT_ROLE
 
    metrics = build_metrics()
    results = evaluate(test_cases=test_cases, metrics=metrics)
 
    rows = []
    test_results = getattr(results, "test_results", results)
    for i, tr in enumerate(test_results):
        meta = metadata[i] if i < len(metadata) else {}
        for m in (getattr(tr, "metrics_data", None) or []):
            rows.append({
                "prompt_version": PROMPT_VERSION,
                "topic": meta.get("topic", ""),
                "level": meta.get("level", ""),
                "behavior": meta.get("behavior", ""),
                "repeat": meta.get("repeat", ""),
                "metric": getattr(m, "name", ""),
                "score": getattr(m, "score", None),
                "success": getattr(m, "success", None),
                "reason": (getattr(m, "reason", "") or "").replace("\n", " "),
            })
 
    raw_path = f"eval_rohdaten_{PROMPT_VERSION}.csv"
    with open(raw_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["prompt_version", "topic", "level",
                                          "behavior", "repeat", "metric",
                                          "score", "success", "reason"])
        w.writeheader()
        w.writerows(rows)
 
    agg = defaultdict(list)
    for r in rows:
        if r["score"] is not None:
            agg[(r["behavior"], r["metric"])].append((r["score"], r["success"]))
 
    agg_path = f"eval_aggregat_{PROMPT_VERSION}.csv"
    with open(agg_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["behavior", "metric", "avg_score", "pass_rate", "n"])
        for (behavior, metric), vals in sorted(agg.items()):
            scores = [v[0] for v in vals]
            passes = [1 for v in vals if v[1]]
            w.writerow([behavior, metric,
                        round(sum(scores) / len(scores), 3),
                        round(len(passes) / len(vals), 3),
                        len(vals)])
 
    print(f"\nFertig. Rohdaten -> {raw_path}\nAggregat  -> {agg_path}")
 
 
if __name__ == "__main__":
    main()