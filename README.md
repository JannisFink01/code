# Evaluation eines sokratischen RAG-Tutors

Automatisierte Evaluation eines Retrieval-Augmented-Generation-Tutors (RAG), der
Studierende der Elektrotechnik/Elektronik **sokratisch** (durch Rückfragen, ohne die
Lösung zu verraten) begleitet. Die Bewertung erfolgt vollautomatisch mit
[DeepEval](https://docs.confident-ai.com/) nach dem Prinzip *LLM-as-a-Judge*.

Das Projekt beantwortet zwei getrennte Forschungsfragen:

- **RQ1 – Sokratische Qualität:** Wie gut führen verschiedene *System-Prompts* den
  Tutor zu sokratischem Verhalten? (Bewertung über eigene G-Eval-Kriterien.)
- **RQ2 – Retrieval-Qualität:** Wie gut arbeitet die RAG-Komponente unter
  verschiedenen *Retrieval-Konfigurationen*? (Bewertung über native RAG-Metriken.)

Beide Fragen laufen als **eigene Pipelines** mit eigenem Konversations-Cache, eigenen
CSVs und eigener Auswertung.

> **Für neue Teammitglieder:** Lies Abschnitt [1](#1-grundidee-der-pipeline) (Grundidee),
> [2](#2-datenfluss--wer-ruft-wen) (Datenfluss) und [4](#4-schnellstart) (Schnellstart) –
> danach kannst du das Projekt starten. Zum **Erweitern** (neuer Prompt, neue RAG-Konfig,
> neues Szenario, neue Metrik) genügt Abschnitt [8](#8-projekt-erweitern). Alle
> Stolperfallen stehen gebündelt in Abschnitt [10](#10-bekannte-fallstricke).

---

## 1. Grundidee der Pipeline

Die Evaluation läuft in **zwei Phasen**, die bewusst getrennt sind, weil sie
unterschiedlich teuer sind:

```
   Phase 1: SIMULIEREN                    Phase 2: BEWERTEN
   ------------------                     -----------------
   Simulator-LLM spielt Studierende  ->   Judge-LLM bewertet die
   im Dialog mit dem RAG-Tutor            gespeicherten Dialoge
   (lokal, günstig)                       (teuer / limitiert)
        |                                        |
        v                                        v
   Konversationen als JSON  --------------->  Metriken -> CSV -> Auswertung
   (Cache, wiederverwendbar)
```

Der **Cache ist der zentrale Trick:** Eine einmal simulierte Konversation wird als JSON
gespeichert (`persistence/konversationen/`) und beim nächsten Lauf **nicht neu erzeugt**.
Man kann also beliebig oft neu *bewerten* (mit anderen Metriken oder einem anderen
Judge), ohne erneut zu simulieren. Über die Umgebungsvariable `RUN_EVALUATION=false`
lässt sich die Bewertung komplett abschalten (nur simulieren).

### Drei Rollen – drei Modelle

| Rolle | Aufgabe | Modul / Client | Grundsatz |
|-------|---------|----------------|-----------|
| **Tutor / SUT** | das zu bewertende System (RAG-Tutor) | `rag_client.py` → Open-WebUI-Pipeline | ist der Prüfling |
| **Simulator** | spielt die studierende Person | `clients.simulator_llm` (`GWDGModel`) | darf günstig/lokal sein |
| **Judge** | bewertet die Dialoge | `clients.judge_llm` (`GWDGModel`) | **muss ein anderes Modell als der Tutor sein** |

> **Wichtiger methodischer Grundsatz – Judge ≠ SUT.** Der Judge darf nicht dasselbe
> Modell sein wie der bewertete Tutor, sonst entsteht ein *Self-Enhancement- /
> Self-Preference-Bias* (Zheng et al. 2023; Wataoka et al. 2024): Ein Modell bewertet
> seine eigenen Ausgaben systematisch zu gut. **Für RQ1 und RQ2 immer denselben Judge
> verwenden**, sonst sind die Ergebnisse nicht vergleichbar.
>
> **Achtung bei den Hochschul-Modellen:** Prüfe die Modellkarte des Endpunkts. Als
> `gpt-4o`/`gpt-4o-mini` angebotene Aliase können in Wahrheit auf dasselbe Modell wie
> der Tutor zeigen (z. B. ein Gemma-Alias, `owned_by: google`) – dann sind sie als
> Judge **ungeeignet**. Als Judge nur ein tatsächlich verschiedenes Modell oder einen
> externen Anbieter wählen.

---

## 2. Datenfluss – wer ruft wen

So hängen die Module zusammen (von oben nach unten = Aufrufrichtung):

```
test_neu.py                     Einstiegspunkt: rq1 | rq2 | both, Startup-Check, Logging
  │
  ├─ clients.py                 baut EINMAL: simulator_llm, judge_llm, tutor_llm,
  │     │                       rag_llm, rate_limiter; lädt kontext.txt
  │     ├─ gwdg_model.py        OpenAI-kompatibler DeepEval-Wrapper (Retry, verify_ssl,
  │     │                       reasoning_effort-Prefix, extra_body)
  │     ├─ rag_client.py        ruft den RAG-Tutor (Open-WebUI-Pipeline) auf
  │     └─ rate_limiter.py      begrenzt Aufrufe/Sekunde und /Minute
  │
  └─ evaluation.run_evaluation(prompt_file, version, rag_config, mode)
        │
        ├─ simulation.simulate_conversations(...)   Phase 1 (Cache-aware, resume-fähig)
        │     ├─ scenarios.build_scenarios()        Themen × Niveau × Verhalten
        │     └─ persistence.save/load_conversations()
        │
        ├─ metrics.build_metrics(judge_llm, mode)   RQ1: 7×GEval + RoleAdherence
        │                                           RQ2: Relevancy + Faithfulness
        ├─ retry_utils.retry_sync(...)              Retry um metric.measure()
        └─ persistence.attach_results(...)          Scores zurück in die Konversations-JSON

auswertung.auswerten()          aggregiert alle Roh-CSVs -> rq1/rq2-Auswertung
```

**Merksatz:** `test_neu.py` orchestriert nur. Die eigentliche Logik steckt in
`simulation.py` (erzeugen), `metrics.py` (bewerten) und `auswertung.py` (aggregieren).
Alles Konfigurierbare liegt in `config.py` und der `.env`.

---

## 3. Verzeichnis- und Dateiüberblick

### Kernmodule (in Aufrufreihenfolge)

| Datei | Zweck |
|-------|-------|
| `test_neu.py` | **Einstiegspunkt.** Startet RQ1, RQ2 oder beides; Startup-Check + Logging (Tee nach `logs/`). |
| `config.py` | Zentrale Konfiguration: Modelle, Endpunkte, `PROMPT_RUNS`, `RAG_CONFIGS`, Pfade, Schwellen. |
| `clients.py` | Erzeugt die LLM-Wrapper (Simulator, Judge, Tutor), den RAG-Client und den Rate-Limiter **einmal** zentral; lädt `kontext.txt`. |
| `gwdg_model.py` | DeepEval-kompatibler LLM-Wrapper um einen OpenAI-kompatiblen Endpunkt (Retry, `verify_ssl`, Reasoning-Prefix, `extra_body`). |
| `rag_client.py` | Ruft den RAG-Tutor auf (inkl. `verbose`-Modus, der den echten `retrieval_context` aus `retrieval.final_chunks[].text` liefert). |
| `scenarios.py` | Testszenarien: Themen × Niveau × Studierenden-Verhalten + feste Einstiegsfragen. |
| `simulation.py` | Führt die Dialog-Simulation aus (resume-fähig, speichert pro Konversation **atomar**). |
| `metrics.py` | Baut die Metriken **je nach `mode`** (`rq1` = GEval + RoleAdherence, `rq2` = native RAG-Metriken). |
| `evaluation.py` | Orchestriert einen Lauf: simulieren (oder laden) → bewerten → CSV schreiben → Scores an JSON anhängen. |
| `persistence.py` | Speichert/lädt Konversationen als JSON (Doppel-Simulations-Schutz), hängt Scores an. |
| `rate_limiter.py` | Begrenzt Aufrufe pro Sekunde/Minute (sync + async). |
| `retry_utils.py` | `retry_sync` / `retry_async` mit linear steigender Wartezeit; `is_transistent_api_error`. |
| `auswertung.py` | Aggregiert die Roh-CSVs zu `rq1_prompt_auswertung.csv` bzw. `rq2_rag_auswertung.csv`. |

### Prompts, Kontext, Szenarien

| Pfad | Inhalt |
|------|--------|
| `prompts/no_Prompt.txt` | Baseline ohne sokratische Steuerung (Referenz). |
| `prompts/minimaler_sokrat.txt` | Minimaler sokratischer Prompt (nur Kernanweisung). |
| `prompts/system_prompt.txt` | Strukturierter sokratischer Prompt (vollständiger Dialogablauf). **Fester Prompt für RQ2.** |
| `prompts/stock_prompt.txt` | Domänenspezifischer In-Lab-Tutorprompt (Fehlerhypothesen, Eskalationsregeln). |
| `prompts/*_context.txt` | Kontext-Varianten – in `config.PROMPT_RUNS` aktuell **auskommentiert**. |
| `kontext.txt` | Fachlicher Kontext, wird von `clients.py` geladen (`KONTEXT_FILE`). **Muss existieren.** |

### Hilfs- und Analyseskripte

| Datei | Zweck |
|-------|-------|
| `visualization/visualize.ipynb` | Notebook zur **RQ1**-Auswertung (Mittelwerte, Streuung, Prompt-Vergleich, Radar/Balken). |
| `visualization/rq2.ipynb` | Notebook zur **RQ2**-Auswertung (Abdeckung/Coverage, Relevanz, effektiver Score). |
| `visualization/*.png`, `*.html` | Erzeugte Diagramme (statisch bzw. interaktiv). |
| `visualization/metrik_beschreibungen.md` | Kurzbeschreibung der Metriken für die Diagramme. |
| `scripts/dialog_compact.py` | Exportiert Konversationen lesbar (Themen als Überschriften, mit ID) → `*_dialoge.md`. |
| `scripts/rag_smoke_test.py` | Schneller Direkttest des RAG-Endpunkts (ohne DeepEval). |
| `test_rag_client.py` | Pytest-Tests für den RAG-Client (Parsing von Antwort + Quellenblock). |
| `entferne_konversationen.py` | Entfernt bestimmte `conversation_id`s sauber aus JSON **und** CSV (legt `.bak` an) → werden neu simuliert/bewertet. |
| `DOKUMENTATION.md` | Ausführliche konzeptionelle Doku (Grundidee, drei Rollen, Metriken). |
| `Dokumentation/` | LaTeX-Quellen der schriftlichen Arbeit (`main.tex`, `references.bib`, …). |

### Erzeugte Daten (nicht versionieren – stehen in `.gitignore`)

```
persistence/
  konversationen/   # simulierte Dialoge als JSON  (Cache, teils >100 MB)
  csv/              # Roh- und Aggregat-CSVs pro Lauf
logs/               # Lauf-Logs (Tee aus stdout/stderr)
rq1_prompt_auswertung.csv   # von auswertung.py im Projektwurzelverzeichnis
rq2_rag_auswertung.csv
```

> Die JSON-Caches können sehr groß werden (>100 MB, GitHub-Limit). `persistence/`,
> `logs/`, `scripts/*.json` und `visualization/eval*.csv`/`rq2*.csv` gehören in die
> `.gitignore` (dort bereits eingetragen). Roher RAG-Antwort-Text sollte **nicht** pro
> Turn unbegrenzt gespeichert werden, sonst wachsen die JSONs unkontrolliert.

---

## 4. Schnellstart

Voraussetzung: Python ≥ 3.10 (getestet mit CPython 3.13/3.14).

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

pip install -r requirements.txt
```

> `requirements.txt` ist ein vollständiger `pip freeze` (u. a. `deepeval==4.0.6`,
> `openai`, `python-dotenv`, `pydantic`, `httpx`, `requests`, `torch`, Jupyter). Die
> Datei ist **UTF‑16** kodiert – nicht als UTF‑8 öffnen/bearbeiten, sonst wird sie
> unlesbar. Zum Neu-Erzeugen: `pip freeze > requirements.txt`.

Dann eine `.env` anlegen (siehe Abschnitt 5) und starten:

```bash
python test_neu.py rq1    # RQ1: Prompt-Vergleich (sokratische Qualität)
python test_neu.py rq2    # RQ2: RAG-Konfig-Vergleich (Retrieval-Qualität)
python test_neu.py both   # beides nacheinander
```

Ablauf jedes Laufs:

1. **Startup-Check** – prüft Erreichbarkeit von Simulator + Judge (je ein Test-Call) und
   dass alle Prompt-Dateien existieren. Bei Fehler: sauberer Abbruch.
2. **Simulation** – erzeugt (oder lädt aus dem Cache) die Dialoge.
3. **Bewertung** – nur wenn `RUN_EVALUATION=true`; wendet die zum `mode` passenden
   Metriken an.
4. **Auswertung** – `auswertung.auswerten()` aggregiert die CSVs.

Alle Ausgaben landen zusätzlich in `logs/lauf_<zeitstempel>.log`.

### Typischer Workflow bei knappem Judge-Budget

```bash
# 1) Erst nur simulieren (günstig, lokal) – Judge nicht nötig
RUN_EVALUATION=false python test_neu.py both
# 2) Später bewerten, wenn ein gültiger Judge verfügbar ist – Cache wird wiederverwendet
RUN_EVALUATION=true  python test_neu.py both
```

---

## 5. Konfiguration (`.env`)

Alle Einstellungen kommen aus einer `.env`-Datei (geladen in `config.py` via
`python-dotenv`). Es gibt **vier getrennte Endpunkte**: GWDG (Default, u. a. Tutor-Modell),
Simulator, Judge und Open-WebUI (RAG). Minimalbeispiel:

```ini
# --- GWDG / Default-Endpunkt (Tutor-Modell, Fallback für Simulator/Judge) ---
GWDG_API_KEY=dein-key
GWDG_BASE_URL=https://chat-ai.academiccloud.de/v1   # muss auf /v1 enden, NICHT /chat/completions

# --- Simulator-Endpunkt (spielt die studierende Person) ---
SIMULATOR_BASE_URL=https://.../v1
SIMULATOR_API_KEY=...

# --- Judge-Endpunkt (bewertet; MUSS != Tutor sein) ---
JUDGE_BASE_URL=https://.../v1
JUDGE_API_KEY=...

# --- Open-WebUI / RAG-Tutor (System unter Test) ---
OPENWEBUI_BASE_URL=https://10.x.x.x:8080/...   # NICHT '/api/chat/completions' anhängen
OPENWEBUI_API_KEY=...

# --- Modelle (Defaults siehe config.py) ---
TUTOR_MODEL=gemma-4-31b-it
SIMULATOR_MODEL=gpt-4o-mini
JUDGE_MODEL=gpt-4.1
RAG_MODEL=qdrant_openwebui_rag_pipeline_rerank_moodle
REASONING_EFFORT=low        # low/medium/high/xhigh – nur für Reasoning-Judges relevant

# --- Bewertung ---
RUN_EVALUATION=true         # false = nur simulieren, nicht bewerten
THRESHOLD=0.7               # Schwelle, ab der ein Kriterium als bestanden gilt (0..1)
REPEATS=1                   # Wiederholungen pro Szenario
MAX_USER_SIMULATIONS=6      # max. Nutzer-Turns pro Dialog

# --- Rate-Limit / Retry (Defaults in config.py) ---
RATE_CALLS_PER_SECOND=3
RATE_CALLS_PER_MINUTE=60
BASE_WAIT=20               # Start-Wartezeit für Retries (Sekunden, linear steigend bis CAP)
CAP=180
MAX_RETRIES=10
```

SSL-Verhalten steht fest im Code (`config.py`), nicht in der `.env`:
`JUDGE_VERIFY_SSL=True`, `SIMULATOR_VERIFY_SSL=False`, `RAG_VERIFY_SSL=False`. Bei
self-signed Zertifikaten arbeitet der jeweilige Client mit `verify=False`.

**Stolperfallen bei der `.env`:**

- `*_BASE_URL` muss am `/v1` (bzw. am Port) enden – **kein** `/chat/completions`
  anhängen, sonst doppelter Pfad → HTTP 405. `config.validate()` prüft das für GWDG/OpenWebUI.
- `RUN_EVALUATION` wird als String gelesen; der Vergleich lautet
  `os.getenv("RUN_EVALUATION","true").strip().lower() == "true"`. Alles außer exakt
  `true` (case-insensitive) schaltet die Bewertung **ab**.
- Ist ein externes Judge-Guthaben leer (`429 insufficient_quota` /
  `credit_balance_exhausted`), ist das **kein Code-Fehler**. Aktuell behandelt der Retry
  solche Fehler wie transiente (429) und wiederholt sie – bei leerem Guthaben also
  wiederholt vergeblich; Lauf abbrechen und Guthaben/Judge prüfen. (Siehe Hinweis in
  Abschnitt 10.)

---

## 6. Modelle, Prompts und RAG-Konfigurationen (`config.py`)

Diese drei Listen steuern, **was** verglichen wird. Sie sind der wichtigste Ort zum
Erweitern (siehe Abschnitt 8).

**`PROMPT_RUNS`** – die Prompt-Varianten für RQ1 (aufsteigender Grad didaktischer Steuerung):

| Kurzname | Bedeutung |
|----------|-----------|
| `no_Prompt` | Baseline ohne Systemprompt (Referenz) |
| `minimaler_sokrat` | Minimaler sokratischer Prompt (nur Kernanweisung) |
| `system_prompt` | Strukturierter sokratischer Prompt (vollständiger Dialogablauf) |
| `stock_prompt` | Domänenspezifischer In-Lab-Tutorprompt |

**`RAG_CONFIGS`** – die 9 Retrieval-Konfigurationen für RQ2 (Collections × Retrieval-Modus
× Reranking), z. B. `llm_only`, `labor_dense`, `vorlesung_dense`, `beide_dense`,
`beide_sparse`, `beide_hybrid`, `beide_hybrid_rerank`, `labor_hybrid_rerank`,
`vorlesung_hybrid_rerank`.

**Feste Zuordnung in `test_neu.py`:**
- RQ1 nutzt **eine** feste RAG-Konfig: `RAG_CONFIGS["beide_hybrid_rerank"]`.
- RQ2 nutzt **einen** festen Prompt: `prompts/system_prompt.txt` und iteriert über **alle**
  `RAG_CONFIGS`.

**Versionsname = Trennkriterium RQ1/RQ2:** RQ1-Läufe heißen wie der Prompt-Kurzname
(z. B. `system_prompt`). RQ2-Läufe hängen die Konfig mit `__` an (z. B.
`system_prompt__beide_hybrid_rerank`). `auswertung.py` unterscheidet RQ1 von RQ2 genau an
diesem `__`.

---

## 7. Metriken (`metrics.py`)

### RQ1 – Sokratische Qualität (`mode="rq1"`)

Sieben `ConversationalGEval`-Kriterien plus die native `RoleAdherenceMetric` als
Gegenprüfung. Jedes G-Eval-Kriterium hat *evaluation_steps* und eine dreistufige *Rubric*
(Score-Bänder 0–2 / 3–6 / 7–10, von DeepEval normiert auf 0–1):

*Lösung nicht verraten · Sokratische Rückfragen · Schrittweise Lernprogression ·
Niveau-Anpassung · Fachliche Korrektheit · Verständnisförderung/Transfer · Respektvolle
Kommunikation.*

Die Kriterien sind lernpsychologisch fundiert (Kost & Chen 2015; Wood, Bruner & Ross 1976;
Vygotsky 1978). `RoleAdherenceMetric` liest `test_case.chatbot_role` (= `config.CHATBOT_ROLE`).

Die **Aggregation** in `auswertung.py` gewichtet die sieben Kriterien zu einem
*gewichteten sokratischen Score* (Gewichte in `auswertung.GEWICHTE`, Summe = 1.0, größtes
Gewicht: „Lösung nicht verraten") und berechnet eine **Gate-Compliance-Rate**: ein
Gespräch besteht das Gate nur, wenn „Lösung nicht verraten" **und** „Fachliche Korrektheit"
≥ `GATE_THRESHOLD` (0.5) liegen.

### RQ2 – Retrieval-Qualität (`mode="rq2"`)

Zwei native DeepEval-Metriken, die den tatsächlich abgerufenen `retrieval_context`
auswerten: `TurnContextualRelevancyMetric` (Passung Kontext↔Frage) und
`TurnFaithfulnessMetric` (Deckung der Antwort durch den Kontext, Grounding). Angelehnt an
RAGAS (Es et al. 2024).

> **Coverage beachten:** Metrik-Mittelwerte sind bei geringer Abdeckung irreführend.
> Fehlt Kontext (z. B. `llm_only`), vergibt DeepEval eine „Freikarte" (Score 1.0). Deshalb
> in `visualization/rq2.ipynb` zusätzlich die **Abdeckung** (Anteil Antworten mit Kontext)
> und die **effektive Retrieval-Güte** (Abdeckung × Relevanz) auswerten.

**Der `mode` muss durchgereicht werden:** `run_evaluation(..., mode="rq2")` →
`build_metrics(judge_llm, mode="rq2")`. Wird er vergessen, laufen versehentlich die
RQ1-Metriken auf den RQ2-Dialogen. (`test_neu.run_rq2()` setzt `mode="rq2"` bereits korrekt.)

---

## 8. Projekt erweitern

Die vier häufigsten Erweiterungen – jeweils genau **eine** Stelle im Code:

### a) Neuen System-Prompt hinzufügen (RQ1)

1. Prompt-Textdatei unter `prompts/` ablegen, z. B. `prompts/mein_prompt.txt`.
2. In `config.PROMPT_RUNS` ein Tupel `("prompts/mein_prompt.txt", "mein_prompt")`
   ergänzen. Der Kurzname wird zum Versionsnamen in CSV/Cache – **eindeutig und ohne `__`**
   wählen (das `__` ist für RQ2 reserviert).
3. `python test_neu.py rq1` starten. Der neue Prompt wird simuliert und bewertet; die
   anderen kommen aus dem Cache.

### b) Neue RAG-Konfiguration hinzufügen (RQ2)

1. In `config.RAG_CONFIGS` einen Eintrag ergänzen, z. B.:
   ```python
   "labor_sparse": {
       "collections": "hollstein_collection_labor",
       "retrieval": "sparse",
       "is_cross_encoder_rerank": False,
   },
   ```
2. `python test_neu.py rq2` starten. RQ2 iteriert automatisch über alle Einträge; der
   Versionsname erhält das Suffix `__labor_sparse` (daran erkennt die Auswertung, dass es
   RQ2 ist).

### c) Neues Szenario hinzufügen

In `scenarios.py`:
- neues Thema in `TOPICS` **und** passende Einstiegsfragen in `INITIAL_QUESTIONS`
  (Kategorien `default`/`halluzination`/`bias`) ergänzen, oder
- neues Verhalten in `BEHAVIORS` **und** `BEHAVIOR_TO_CATEGORY` ergänzen.

Achte auf konsistente Behavior-Kategorien: `get_initial_question()` bildet Verhalten über
`BEHAVIOR_TO_CATEGORY` auf eine Fragenkategorie ab. Fehlt der Eintrag, fällt es auf
`default` zurück.

> **Stichprobengröße im Blick behalten:** `build_scenarios()` erzeugt aktuell
> 3 Themen × 5 Verhalten (Anfänger) **+** 3 Themen × 3 Verhalten (Fortgeschritten, nur
> `BEHAVIORS[2:]`) = **24 Szenarien** × `REPEATS`. Die Niveaus sind also **asymmetrisch**
> (Fortgeschritten deckt nur einen Teil der Verhalten ab). Vor der finalen Auswertung
> entscheiden, ob das gewollt ist.

### d) Neue Metrik / neues Kriterium

In `metrics.build_metrics(...)` im passenden `mode`-Zweig ergänzen. Für ein G-Eval-Kriterium
immer *evaluation_steps* **und** *Rubric* (drei Bänder) angeben und die didaktische
Fundierung dokumentieren. Nimmst du ein Kriterium in die RQ1-Auswertung auf, ergänze auch
`auswertung.GEWICHTE` (Summe der Gewichte im Blick behalten) und ggf. `GATE_METRIKEN`.

### e) Judge wechseln

Nur `JUDGE_MODEL` und den Judge-Endpunkt (`JUDGE_BASE_URL`/`JUDGE_API_KEY`) ändern.
Grundsatz **Judge ≠ Tutor** beachten. Ist der Judge ein Reasoning-Modell, `REASONING_EFFORT`
niedrig setzen (sonst lange Antwortzeiten). Auf self-signed Endpunkten `JUDGE_VERIFY_SSL`
in `config.py` auf `False` setzen. **Wichtig:** Wenn du den Judge nach vorhandenen
Auswertungen wechselst, sind alte und neue Scores nicht mehr vergleichbar – betroffene
Roh-CSVs löschen und neu bewerten (Konversationen bleiben im Cache, müssen nicht neu
simuliert werden).

---

## 9. Cache, Resume und Wartung

- **Resume:** Die Zuordnung Cache↔Szenario erfolgt deterministisch über eine stabile
  `conversation_id` (SHA1 aus `version|topic|level|behavior|repeat`). Wird ein Lauf
  unterbrochen, setzt der nächste Start dort fort, wo aufgehört wurde – sowohl bei der
  Simulation (bereits gespeicherte IDs werden übersprungen) als auch bei der Bewertung
  (bereits in der Roh-CSV stehende `(topic, behavior, repeat)` werden übersprungen).
- **Atomar speichern:** `simulation.py` schreibt die Konversations-JSON nach **jedem**
  Gespräch atomar (Temp-Datei + `os.replace`). Ein Absturz kostet höchstens das gerade
  laufende Gespräch.
- **Nur bestimmte Gespräche neu machen:** `entferne_konversationen.py` entfernt gezielte
  `conversation_id`s aus JSON **und** CSV (mit `.bak`-Backup). Beim nächsten Lauf werden sie
  neu simuliert und bewertet.
- **Lesbarer Export:** `scripts/dialog_compact.py` erzeugt aus einer Konversations-JSON ein
  Markdown mit Themen-Überschriften und IDs.
- **Neue Bewertung ohne Neu-Simulation:** Roh-/Aggregat-CSVs löschen (oder verschieben,
  vgl. `persistence/csv/oldrq2/`), Konversations-JSON behalten, erneut mit
  `RUN_EVALUATION=true` starten.

---

## 10. Bekannte Fallstricke

- **`retrieval_context` nur im verbose-Modus:** Der echte Chunk-Text kommt ausschließlich
  aus der Verbose-JSON der Pipeline (`retrieval.final_chunks[].text`). Der normale
  Antwortmodus liefert nur Quellen-**Metadaten** (Dateiname/Collection/Chunk/Score), **nicht**
  den Text – damit wären die RQ2-Metriken nicht berechenbar. `simulation.py` ruft den
  RAG-Client deshalb mit `verbose=True` auf.
- **`retrieval_context = None` → Absturz:** Metriken lesen `turn.retrieval_context`. Fehlt
  Kontext, wird bewusst `[]` gesetzt (nicht `None`), sonst NoneType-Fehler.
- **LaTeX in Dialogen:** Backslashes im Dialogtext brechen das JSON-Parsing des Judge
  (`Invalid \escape`). `evaluation._delatexe` erzeugt vor der Bewertung eine bereinigte
  Kopie; die Simulation muss dafür **nicht** neu laufen.
- **CSV-Feldgröße:** `verbose_logs`/lange Reasons nicht ungefiltert in die CSV schreiben.
  Beide CSV-lesenden Module setzen `csv.field_size_limit(...)` hoch (10 Mio bzw. 100 Mio).
- **Große Dateien / Git:** `persistence/`, `logs/`, `scripts/*.json` und
  `visualization/eval*.csv`/`rq2*.csv` sind in `.gitignore`. Keine mehrere-100-MB-JSONs
  committen (die JSONs in `scripts/` sind bereits >100 MB).
- **Endpunkt-Pfad (405):** `*_BASE_URL` niemals mit `/chat/completions` bzw.
  `/api/chat/completions` enden lassen (siehe Abschnitt 5).
- **Quota-/Billing-Fehler:** Externe Judge-Guthaben-Fehler (`insufficient_quota`,
  `credit_balance_exhausted`) enthalten „429" und werden vom aktuellen Retry als transient
  behandelt – d. h. mehrfach vergeblich wiederholt. Bei leerem Guthaben Lauf abbrechen und
  Judge/Guthaben prüfen, statt auf einen erfolgreichen Retry zu warten.
- **`mode` durchreichen (RQ2):** siehe Abschnitt 7 – ohne `mode="rq2"` laufen die
  RQ1-Metriken auf RQ2-Dialogen.
- **RQ2-Freikarte:** Konfigurationen ohne Kontext (v. a. `llm_only`) bekommen von DeepEval
  Score 1.0. Für einen fairen Vergleich Abdeckung und effektive Retrieval-Güte heranziehen
  (`visualization/rq2.ipynb`), nicht die nackten Mittelwerte.
- **`requirements.txt` ist UTF‑16:** nicht versehentlich als UTF‑8 speichern.

---

## 11. Literatur (Kurzform)

Zheng et al. 2023 (LLM-as-a-Judge, Bias) · Wataoka et al. 2024 (Self-Preference Bias) ·
Liu et al. 2023 (G-Eval) · Es et al. 2024 (RAGAS) · Kost & Chen 2015 (sokratisches
Tutoring) · Wood, Bruner & Ross 1976 (Scaffolding) · Vygotsky 1978 (ZPD). Vollständige
Angaben in `Dokumentation/references.bib`; ausführliche konzeptionelle Erklärung in
`DOKUMENTATION.md`.
