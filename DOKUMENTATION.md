# Evaluierung sokratischer System-Prompts mit DeepEval

Dokumentation zum Aufbau, der bewertet, **wie gut eine KI sokratische Dialoge
führt**. Statt einen vorgefertigten Dialog zu benoten, wird der Dialog live
erzeugt: Ein simulierter Student stellt Fragen, die zu testende KI antwortet mit
deinem System-Prompt, und ein Judge-Modell bewertet das Ergebnis.

---

## 1. Grundidee

DeepEval **erzeugt von sich aus keine Dialoge — es bewertet sie nur.** Wer also
testen will, wie gut ein System-Prompt einen sokratischen Tutor macht, muss zwei
Schritte trennen:

1. **Generieren** – das Gespräch entsteht durch den `ConversationSimulator`.
2. **Bewerten** – das erzeugte Gespräch wird mit konversationellen Metriken
   (LLM-as-judge) bewertet.

Ein häufiger Anfangsfehler ist, einen handgeschriebenen Dialog aus einer JSON zu
bewerten. Das misst nur den vorgegebenen Text, nicht die Fähigkeit der KI.

---

## 2. Die drei Rollen

Im Aufbau wirken drei Modell-Rollen zusammen. Sie können dasselbe Modell sein
oder verschiedene:

| Rolle | Wo im Code | Aufgabe |
|---|---|---|
| **Tutor (zu testendes Modell)** | `model_callback`, mit dem System-Prompt | Führt den sokratischen Dialog – das, was bewertet wird |
| **Simulierter Student** | `simulator_model` im `ConversationSimulator` | Spielt die studierende Person, erzeugt die Nutzerfragen |
| **Judge** | `model=` in jeder Metrik | Vergibt die Scores |

Der **System-Prompt gehört in den `model_callback`** – das ist die einzige
Stelle, an der er definiert wird. In den `Turn`-Objekten selbst gibt es keine
`system`-Rolle (nur `user` und `assistant`).

---

## 3. Voraussetzungen

```bash
pip install deepeval openai python-dotenv
```

API-Key und Modell gehören in eine `.env` (nicht in den Code):

```
OPENAI_API_KEY=dein-key
# Optional fuer OpenAI-kompatible Endpunkte (z.B. GWDG/gemma):
# OPENAI_BASE_URL=https://chat-ai.academiccloud.de/v1
```

Laden im Skript:

```python
from dotenv import load_dotenv
load_dotenv()
```

> **Sicherheit:** API-Keys niemals fest ins Skript schreiben oder teilen. Ein
> versehentlich offengelegter Key muss widerrufen werden.

---

## 4. Aufbau des Skripts (Schritt für Schritt)

### 4.1 System-Prompt laden

```python
with open("system_prompt.txt", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()
```

### 4.2 Die zu testende KI als Callback

Hier wird der System-Prompt eingesetzt. `input` ist die Nachricht des
simulierten Studenten, `turns` der bisherige Verlauf (für Kohärenz wichtig).

```python
from openai import OpenAI
from deepeval.test_case import Turn

client = OpenAI()   # fuer gemma: OpenAI(base_url="https://.../v1")

async def model_callback(input: str, turns: list[Turn] = None, thread_id: str = None) -> Turn:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for t in (turns or []):
        messages.append({"role": t.role, "content": t.content})
    messages.append({"role": "user", "content": input})

    resp = client.chat.completions.create(model="gpt-4o", messages=messages)
    return Turn(role="assistant", content=resp.choices[0].message.content)
```

### 4.3 Szenario definieren (`ConversationalGolden`)

Kein fertiger Dialog mehr – nur die Ausgangslage. Der Simulator baut daraus das
Gespräch.

```python
from deepeval.dataset import ConversationalGolden

golden = ConversationalGolden(
    scenario="Ein Studierender versteht nicht, was die Sperrspannung einer Z-Diode mit dem Nichtleiten zu tun hat.",
    expected_outcome="Der Studierende kommt durch sokratische Rückfragen selbst auf die Erklärung; die Lösung wird nie direkt verraten.",
    user_description="Elektrotechnik-Studierender im 1. Semester, unsicher, stellt einfache Fragen.",
)
```

Mehrere Test-Szenarien = mehrere `ConversationalGolden` in der Liste.

### 4.4 Dialog simulieren

```python
from deepeval.simulator import ConversationSimulator

simulator = ConversationSimulator(model_callback=model_callback, simulator_model="gpt-4o")
test_cases = simulator.simulate(conversational_goldens=[golden], max_user_simulations=5)
```

`max_user_simulations` begrenzt die Anzahl der Frage-Antwort-Runden.
`simulate()` gibt eine Liste fertiger `ConversationalTestCase`s zurück.

### 4.5 Metriken definieren und bewerten

```python
from deepeval import evaluate
from deepeval.test_case import MultiTurnParams
from deepeval.metrics import ConversationalGEval

sokratisch = ConversationalGEval(
    name="Sokratische Führung",
    evaluation_steps=[
        "Pruefe, ob der Assistent ueberwiegend mit leitenden Rueckfragen antwortet, statt zu dozieren.",
        "Bestrafe stark, wenn die Loesung direkt verraten oder eine Vermutung bestaetigt wird.",
        "Belohne, wenn auf die Antworten der studierenden Person aufgebaut wird.",
    ],
    evaluation_params=[MultiTurnParams.CONTENT],
    model="gpt-4o",
    threshold=0.7,
)

evaluate(test_cases=test_cases, metrics=[sokratisch])
```

---

## 5. Verfügbare konversationelle Metriken

Ein `ConversationalTestCase` kann **nur** mit konversationellen Metriken
bewertet werden (RAG-Metriken wie Faithfulness funktionieren hier nicht):

| Metrik | Misst | Besonderheit |
|---|---|---|
| **ConversationalGEval** | Eigene Kriterien in Alltagssprache | Ideal für „sokratisch": stellt Rückfragen, verrät Lösung nicht |
| **ConversationRelevancyMetric** | Relevanz der Antworten zu den Nutzerfragen | je nach Version `TurnRelevancyMetric` |
| **ConversationCompletenessMetric** | Erfüllt das Gespräch das Ziel | nutzt `scenario`/`expected_outcome` |
| **RoleAdherenceMetric** | Bleibt der Bot in seiner Rolle | braucht `chatbot_role` (sonst Fehler) |
| **KnowledgeRetentionMetric** | Behält der Bot Gesagtes über Turns | nur bei echten Folgefragen sinnvoll |

Alle sind LLM-as-judge und brauchen `model=` (das Judge-Modell).

Für den sokratischen Use-Case sind **ConversationalGEval** und
**ConversationRelevancyMetric** am aussagekräftigsten.

---

## 6. Ausführen

```bash
python test_neu.py
```

Hinweis: Da das Skript am Ende einfach `evaluate(...)` aufruft, läuft es mit
`python <datei>.py` direkter als mit `deepeval test run` – letzteres ist für
Pytest-Testfunktionen gedacht und meldet sonst „No test cases found".

---

## 7. Ergebnisse lesen

Jede Metrik liefert:

- **Score (0–1):** je höher, desto besser. Bestanden, wenn `score >= threshold`.
- **Reason:** Begründung des Judge im Klartext – das Wertvollste zum Verstehen,
  *warum* ein Score zustande kam.
- **Status:** PASSED / FAILED / ERRORED.

Beispiel: „Sokratische Führung 0.60 (FAILED)" mit Begründung, dass der Tutor in
der letzten Antwort die Lösung bestätigt hat – ein konkreter, umsetzbarer
Hinweis zur Prompt-Verbesserung.

---

## 8. Erweitern

- **Mehr Szenarien:** weitere `ConversationalGolden` in die Liste – verschiedene
  Themen, Schwierigkeitsgrade, schwierige Studierende.
- **Prompts vergleichen:** zwei `system_prompt`-Varianten laden, jeweils
  simulieren und bewerten, Scores gegenüberstellen.
- **Anderes Modell (gemma/GWDG):** `OPENAI_BASE_URL` setzen und im `client`
  übergeben; als Judge/Simulator ggf. einen `DeepEvalBaseLLM`-Wrapper nutzen
  (nötig, weil ein bloßer Modell-String immer zur echten OpenAI-API geht).

---

## 9. Häufige Fehler (aus der Praxis)

| Fehler / Meldung | Ursache | Lösung |
|---|---|---|
| `object of type 'NoneType' has no len()` | `turns=` nicht an `ConversationalTestCase` übergeben | `turns=turns` ergänzen |
| `Metric Faithfulness is not a valid metric for ConversationalTestCase` | RAG-Metriken bei Multi-Turn | konversationelle Metriken benutzen |
| `'chatbot_role' ... cannot be empty for the 'Role Adherence' metric` | `chatbot_role` fehlt | `chatbot_role="..."` setzen |
| `name 'MultiTurnParams' is not defined` | Import fehlt | `from deepeval.test_case import MultiTurnParams` |
| `TypeError: str expected, not tuple` | Komma am Zeilenende (`= "...",`) macht ein Tuple | Komma entfernen |
| Alle Turns sind `assistant` | falscher Schlüssel beim Rollen-Mapping (`speaker` vs. anderes) | korrekten Feldnamen verwenden |
| `expected_output` wird ignoriert | falscher Param-Name | bei Konversation heißt es `expected_outcome` |
| `ConnectTimeout` / Request timed out | Server nicht erreichbar (VPN/Firewall) | Netz/VPN prüfen (`Test-NetConnection host -Port port`) |

---

## 10. Kurz-Checkliste

1. `.env` mit Key (und ggf. `OPENAI_BASE_URL`) vorhanden, `load_dotenv()` aufgerufen.
2. `SYSTEM_PROMPT` geladen und im `model_callback` als `system`-Message gesetzt.
3. Mindestens ein `ConversationalGolden` mit `scenario` + `expected_outcome`.
4. `ConversationSimulator(...).simulate(...)` erzeugt die Test-Cases.
5. Nur konversationelle Metriken, jeweils mit `model=` (Judge).
6. `evaluate(test_cases=..., metrics=...)` und Reason-Begründungen auswerten.
