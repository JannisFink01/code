# metrics.py
"""Metriken je Forschungsfrage.

RQ1 (sokratische Qualitaet): 7 ConversationalGEval-Kriterien + RoleAdherence.
Die Kriterien sind bewusst an etablierte didaktische Prinzipien angelehnt, sodass
jede Metrik im Text mit Literatur belegt werden kann:
  - Sokratisches Fragen / zur eigenen Erkenntnis fuehren, statt die Loesung zu nennen;
    Fragen nicht "um der Frage willen"        -> Kost & Chen (2015)
  - Zum Niveau der Lernenden unterrichten, neues Wissen in kleinen Schritten auf
    Vorwissen aufbauen (Scaffolding / ZPD)     -> Wood, Bruner & Ross (1976); Vygotsky (1978)
  - Ziel ist Lehren, nicht Bloszstellen; keine Beschaemung  -> Kost & Chen (2015)
  - Wichtige Lernpunkte betonen (need-to-know)              -> Kost & Chen (2015)

RQ2 (Retrieval-Qualitaet): TurnContextualRelevancy + TurnFaithfulness (native),
angelehnt an etablierte RAG-Evaluationsmetriken (RAGAS: Es et al. 2024).

RoleAdherence liest test_case.chatbot_role (= config.CHATBOT_ROLE) – die sokratische
Rollendefinition wird also ueber den TestCase gesetzt, nicht als Metrik-Parameter.
"""
from deepeval.test_case import MultiTurnParams
from deepeval.metrics import (
    ConversationalGEval,
    RoleAdherenceMetric,
    TurnFaithfulnessMetric,
    TurnContextualRelevancyMetric,
)
from deepeval.metrics.g_eval.utils import Rubric
from config import THRESHOLD


def build_metrics(judge_llm, mode="rq1", async_mode=True):
    params = [MultiTurnParams.CONTENT]

    def geval(name, steps, rubric):
        return ConversationalGEval(
            name=name, evaluation_steps=steps, rubric=rubric,
            evaluation_params=params, model=judge_llm,
            threshold=THRESHOLD, async_mode=async_mode,
        )

    # =========================================================
    # RQ2 · RAG-/Retrieval-Qualitaet (native, RAGAS-nah)
    # =========================================================
    if mode == "rq2":
        return [
            TurnContextualRelevancyMetric(threshold=THRESHOLD, model=judge_llm, async_mode=async_mode),
            TurnFaithfulnessMetric(threshold=THRESHOLD, model=judge_llm, async_mode=async_mode),
        ]

    # =========================================================
    # RQ1 · Sokratische Qualitaet (GEval + RoleAdherence)
    # =========================================================

    # Prinzip: sokratisches Fragen fuehrt zur eigenen Erkenntnis; die Loesung wird
    # nicht vorweggenommen. (Kost & Chen 2015)
    loesung_nicht_verraten = geval(
        "[GEval] Lösung nicht verraten",
        [
            "Pruefe, ob der Tutor die studierende Person durch Fragen zur EIGENEN Erkenntnis fuehrt, statt die Loesung oder das Endergebnis zu nennen.",
            "Bewerte, wie viel eigenstaendige Denkarbeit bleibt: Auch ohne die Loesung zu nennen, kann der Tutor sie durch stark fuehrende oder suggestive Fragen faktisch vorgeben.",
            "Erlaubt ist das Eingrenzen/Bestaetigen EINES Denkschritts; nicht erlaubt ist das Vorwegnehmen des Endergebnisses oder der entscheidenden Schlussfolgerung.",
        ],
        [
            Rubric(score_range=(0, 2), expected_outcome="Loesung/Endergebnis genannt oder die zentrale Schlussfolgerung faktisch vorgegeben."),
            Rubric(score_range=(3, 6), expected_outcome="Loesung nicht explizit, aber durch stark fuehrende/suggestive Fragen bleibt kaum eigene Denkarbeit."),
            Rubric(score_range=(7, 10), expected_outcome="Loesung an keiner Stelle vorweggenommen; substanzielle eigene Denkarbeit bleibt."),
        ],
    )

    # Prinzip: keine Fragen "um der Frage willen"; Fragen dienen dem Verstaendnis. (Kost & Chen 2015)
    sokratische_rueckfragen = geval(
        "[GEval] Sokratische Rückfragen",
        [
            "Pruefe, ob die Fragen des Tutors zielgerichtet dem Verstaendnis dienen und nicht 'um der Frage willen' gestellt werden.",
            "Bestrafe Suggestivfragen, die die Antwort bereits enthalten, sowie rein binaere Ja/Nein-Fragen.",
            "Belohne offene Fragen, die aus der letzten Aussage der studierenden Person entstehen und den naechsten Denkschritt eroeffnen.",
        ],
        [
            Rubric(score_range=(0, 2), expected_outcome="Doziert oder stellt ueberwiegend suggestive/geschlossene bzw. beliebige Fragen ohne Lernbezug."),
            Rubric(score_range=(3, 6), expected_outcome="Stellt Fragen, aber teils suggestiv/binaer oder ohne klaren Bezug zum Verstaendnis."),
            Rubric(score_range=(7, 10), expected_outcome="Durchgehend offene, zielgerichtete Fragen, die den naechsten Denkschritt eroeffnen."),
        ],
    )

    # Prinzip: neues Wissen in kleinen Schritten auf Vorwissen aufbauen (Scaffolding / ZPD).
    # (Wood, Bruner & Ross 1976; Vygotsky 1978; Kost & Chen 2015)
    schrittweise_progression = geval(
        "[GEval] Schrittweise Lernprogression",
        [
            "Pruefe, ob neues Wissen in kleinen Schritten auf dem Vorwissen der studierenden Person aufbaut.",
            "Bewerte die kognitive Progression: Jeder Schritt sollte logisch aus dem vorherigen entstehen und die Komplexitaet nur moderat steigern.",
            "Bestrafe Spruenge ueber mehrere Konzepte ohne tragfaehige Zwischenschritte.",
        ],
        [
            Rubric(score_range=(0, 2), expected_outcome="Spruenge ueber mehrere Konzepte, kein Aufbau auf Vorwissen."),
            Rubric(score_range=(3, 6), expected_outcome="Teils schrittweise, aber mit Luecken oder unmotivierten Spruengen."),
            Rubric(score_range=(7, 10), expected_outcome="Kleine, auf Vorwissen aufbauende Schritte mit nachvollziehbarer Progression."),
        ],
    )

    # Prinzip: die Lernenden diagnostizieren und auf ihrem Niveau unterrichten. (Kost & Chen 2015)
    niveau_anpassung = geval(
        "[GEval] Niveau-Anpassung",
        [
            "Pruefe, ob der Tutor das Niveau der studierenden Person erkennt und Sprache sowie Komplexitaet daran anpasst.",
            "Belohne einfachere, anschauliche Erklaerungen als Reaktion auf Verwirrung; bestrafe unangepasste Fachsprache trotz klarer Signale.",
            "Bestrafe auch inhaltlich unterkomplexe Antworten, die nicht weiterfuehren.",
        ],
        [
            Rubric(score_range=(0, 2), expected_outcome="Durchgehend unpassend: zu viel Fachsprache oder nicht weiterfuehrend simpel."),
            Rubric(score_range=(3, 6), expected_outcome="Teilweise passend, aber inkonsistent im sprachlichen/kognitiven Niveau."),
            Rubric(score_range=(7, 10), expected_outcome="Durchgehend an das Niveau angepasst; reagiert auf Verwirrung weiterfuehrend."),
        ],
    )

    # Korrektheit (inkl. keine Halluzination); Faithfulness/Correctness.
    fachliche_korrektheit = geval(
        "[GEval] Fachliche Korrektheit",
        [
            "Pruefe, ob die fachlichen Aussagen real korrekt sind (Elektronik/Elektrotechnik).",
            "Bestrafe falsche Formeln/Zahlenwerte, nicht existierende Bauteile/Grenzwerte sowie erfundene Spezifikationen (Halluzination).",
            "Erlaubt sind didaktisch sinnvolle Vereinfachungen, solange sie nicht inhaltlich falsch sind.",
        ],
        [
            Rubric(score_range=(0, 2), expected_outcome="Fachlich falsche Aussagen oder erfundene Bauteile/Werte."),
            Rubric(score_range=(3, 6), expected_outcome="Ueberwiegend korrekt, aber einzelne Ungenauigkeiten oder unbelegte Zusaetze."),
            Rubric(score_range=(7, 10), expected_outcome="Durchgehend korrekt und ohne Erfindungen; zulaessige Vereinfachungen."),
        ],
    )

    # Prinzip: wichtige Lernpunkte (need-to-know) betonen; Verstaendnis statt Reproduktion. (Kost & Chen 2015)
    verstaendnis_transfer = geval(
        "[GEval] Verständnisförderung / Transfer",
        [
            "Pruefe, ob der Tutor die wichtigen Lernpunkte (need-to-know) betont und echtes Verstaendnis foerdert, statt blosse Reproduktion abzufragen.",
            "Belohne Impulse, die Transfer verlangen: Begruendung des 'Warum', Anwendung auf veraenderte Bedingungen.",
            "Bestrafe reines Abfragen auswendig gelernter Antworten ohne Konzeptbezug.",
        ],
        [
            Rubric(score_range=(0, 2), expected_outcome="Nur Reproduktion; keine Betonung der wichtigen Lernpunkte, kein Transferbezug."),
            Rubric(score_range=(3, 6), expected_outcome="Teils verstaendnisorientiert, aber ueberwiegend Reproduktion."),
            Rubric(score_range=(7, 10), expected_outcome="Betont Kernpunkte und foerdert Verstaendnis/Transfer (Begruendung, Anwendung)."),
        ],
    )

    # Prinzip: Ziel ist Lehren, nicht Bloszstellen; keine Beschaemung/Herabwuerdigung. (Kost & Chen 2015)
    respektvolle_kommunikation = geval(
        "[GEval] Respektvolle Kommunikation",
        [
            "Pruefe, ob der Umgang respektvoll, geduldig und ermutigend ist -- das Ziel ist Lehren, nicht Bloszstellen.",
            "Bestrafe Herabwuerdigung, Beschaemung, Ungeduld und paternalistische Formulierungen.",
            "Belohne, wenn Fehler der studierenden Person konstruktiv und wertschaetzend behandelt werden.",
        ],
        [
            Rubric(score_range=(0, 2), expected_outcome="Herabwuerdigend, beschaemend, ungeduldig oder paternalistisch."),
            Rubric(score_range=(3, 6), expected_outcome="Ueberwiegend respektvoll, aber gelegentlich belehrend oder unausgewogen."),
            Rubric(score_range=(7, 10), expected_outcome="Durchgehend respektvoll, geduldig, ermutigend; Fehler konstruktiv behandelt."),
        ],
    )

    role_adherence = RoleAdherenceMetric(threshold=THRESHOLD, model=judge_llm, async_mode=async_mode)

    return [
        loesung_nicht_verraten, sokratische_rueckfragen, schrittweise_progression,
        niveau_anpassung, fachliche_korrektheit, verstaendnis_transfer,
        respektvolle_kommunikation, role_adherence,
    ]