# metrics.py
"""Metriken je Forschungsfrage:
  mode="rq1" (sokratische Qualitaet): 7 GEval-Kriterien + RoleAdherence (nativer Gegencheck).
  mode="rq2" (RAG-/Retrieval-Qualitaet): TurnContextualRelevancy + TurnFaithfulness.

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
    # RQ2 · RAG-/Retrieval-Qualitaet (native)
    # =========================================================
    if mode == "rq2":
        return [
            TurnContextualRelevancyMetric(threshold=THRESHOLD, model=judge_llm, async_mode=async_mode),
            TurnFaithfulnessMetric(threshold=THRESHOLD, model=judge_llm, async_mode=async_mode),
        ]

    # =========================================================
    # RQ1 · Sokratische Qualitaet (GEval + RoleAdherence)
    # =========================================================
    keine_loesung = geval(
        "[GEval] Lösung nicht verraten",
        [
            "Pruefe, ob der Tutor die Loesung/das Endergebnis direkt nennt oder eine Vermutung des Studenten explizit als richtig bestaetigt.",
            "Bewerte, wie viel eigenstaendige Denkarbeit dem Studenten noch bleibt: Auch ohne die Loesung zu nennen, kann der Tutor sie durch stark fuehrende/suggestive Fragen faktisch vorgeben.",
            "Erlaubt ist das Eingrenzen/Bestaetigen EINES Denkschritts. Nicht erlaubt ist das Vorwegnehmen des Endergebnisses oder der entscheidenden Schlussfolgerung.",
        ],
        [
            Rubric(score_range=(0, 2), expected_outcome="Loesung/Endergebnis genannt oder die zentrale Schlussfolgerung faktisch vorgegeben."),
            Rubric(score_range=(3, 6), expected_outcome="Loesung nicht explizit, aber durch stark fuehrende/suggestive Fragen bleibt kaum eigene Denkarbeit."),
            Rubric(score_range=(7, 10), expected_outcome="Loesung an keiner Stelle vorweggenommen; dem Studenten bleibt substanzielle eigene Denkarbeit."),
        ],
    )
    gegenfragen = geval(
        "[GEval] Sokratische Rückfragen",
        [
            "Pruefe, ob der Tutor mit echten, offenen Fragen fuehrt statt zu dozieren.",
            "Bestrafe Suggestivfragen, die die Antwort bereits enthalten (z. B. '..., oder?'), und rein binaere Ja/Nein-Fragen.",
            "Belohne Fragen, die aus der letzten Aussage des Studenten entstehen und den naechsten Denkschritt eroeffnen, ohne die Antwort vorzugeben.",
        ],
        [
            Rubric(score_range=(0, 2), expected_outcome="Doziert oder nutzt ueberwiegend suggestive/geschlossene Fragen, die die Antwort vorgeben."),
            Rubric(score_range=(3, 6), expected_outcome="Stellt Fragen, aber teils suggestiv/binaer oder ohne Bezug zur letzten Aussage."),
            Rubric(score_range=(7, 10), expected_outcome="Durchgehend offene, anschlussfaehige Fragen, die den naechsten Denkschritt eroeffnen ohne die Antwort zu enthalten."),
        ],
    )
    schrittweise = geval(
        "[GEval] Schrittweises Vorgehen",
        [
            "Pruefe, ob jeder neue Schritt logisch aus dem vorherigen entsteht und die Komplexitaet nur moderat steigt.",
            "Bewerte die kognitive Progression, nicht bloss die Gespraechsstruktur oder staendiges 'Genau, richtig!'.",
            "Bestrafe Spruenge ueber mehrere Konzepte ohne tragfaehige Zwischenschritte.",
        ],
        [
            Rubric(score_range=(0, 2), expected_outcome="Spruenge ueber mehrere Konzepte, keine tragfaehige Progression."),
            Rubric(score_range=(3, 6), expected_outcome="Teils schrittweise, aber mit Luecken oder unmotivierten Spruengen."),
            Rubric(score_range=(7, 10), expected_outcome="Klare, aufeinander aufbauende kognitive Progression mit moderater Komplexitaetssteigerung."),
        ],
    )
    niveau = geval(
        "[GEval] Niveau-Anpassung",
        [
            "Pruefe, ob Sprache UND kognitives Niveau zur (Anfaenger-)Person passen.",
            "Belohne einfachere, anschauliche Erklaerungen als Reaktion auf Verwirrung; bestrafe unangepasste Fachsprache trotz klarer Signale.",
            "Bestrafe auch inhaltlich unterkomplexe Antworten, die den Studenten nicht weiterfuehren.",
        ],
        [
            Rubric(score_range=(0, 2), expected_outcome="Durchgehend unpassend: zu viel Fachsprache trotz Signalen oder nicht weiterfuehrend simpel."),
            Rubric(score_range=(3, 6), expected_outcome="Teilweise passend, aber inkonsistent im sprachlichen/kognitiven Niveau."),
            Rubric(score_range=(7, 10), expected_outcome="Durchgehend passend; reagiert auf Verwirrung mit anschaulichen, weiterfuehrenden Erklaerungen."),
        ],
    )
    korrektheit = geval(
        "[GEval] Fachliche Korrektheit",
        [
            "Pruefe, ob die fachlichen Aussagen (z. B. Z-Diode, Spannungsstabilisierung, Ohmsches Gesetz) real korrekt sind.",
            "Bestrafe falsche Formeln/Zahlenwerte, nicht existierende Bauteile/Grenzwerte sowie erfundene konkrete Spezifikationen (Halluzination).",
            "Erlaubt sind didaktisch sinnvolle Vereinfachungen fuer Anfaenger, solange sie nicht inhaltlich falsch sind.",
        ],
        [
            Rubric(score_range=(0, 2), expected_outcome="Fachlich falsche Aussagen oder erfundene Bauteile/Werte."),
            Rubric(score_range=(3, 6), expected_outcome="Ueberwiegend korrekt, aber einzelne Ungenauigkeiten oder unbelegte Zusaetze."),
            Rubric(score_range=(7, 10), expected_outcome="Durchgehend korrekt und ohne Erfindungen; zulaessige didaktische Vereinfachungen."),
        ],
    )
    transfer = geval(
        "[GEval] Verständnisförderung / Transfer",
        [
            "Pruefe, ob der Tutor echtes Verstaendnis foerdert und nicht nur das Reproduzieren von Formeln/Begriffen.",
            "Belohne Impulse, die Transfer verlangen: Begruendung des 'Warum', Anwendung auf veraenderte Bedingungen (andere Eingangsspannung/Last).",
            "Bestrafe reines Abfragen auswendig gelernter Antworten ohne Konzeptbezug.",
        ],
        [
            Rubric(score_range=(0, 2), expected_outcome="Nur Reproduktion von Fakten/Formeln, kein Konzept- oder Transferbezug."),
            Rubric(score_range=(3, 6), expected_outcome="Teils verstaendnisorientiert, aber ueberwiegend Reproduktion."),
            Rubric(score_range=(7, 10), expected_outcome="Foerdert durchgehend Verstaendnis und Transfer (Begruendungen, Anwendung auf neue Situationen)."),
        ],
    )
    respekt = geval(
        "[GEval] Respektvolle Kommunikation",
        [
            "Pruefe auf respektvollen, geduldigen und ermutigenden Ton.",
            "Bestrafe Herabwuerdigung, Beschaemung, Ungeduld und paternalistische Formulierungen.",
            "Belohne, wenn Fehler des Studenten konstruktiv und wertschaetzend behandelt werden.",
        ],
        [
            Rubric(score_range=(0, 2), expected_outcome="Herabwuerdigend, beschaemend, ungeduldig oder paternalistisch."),
            Rubric(score_range=(3, 6), expected_outcome="Ueberwiegend respektvoll, aber gelegentlich belehrend oder unausgewogen."),
            Rubric(score_range=(7, 10), expected_outcome="Durchgehend respektvoll, geduldig, ermutigend; Fehler werden konstruktiv behandelt."),
        ],
    )

    role_adherence = RoleAdherenceMetric(threshold=THRESHOLD, model=judge_llm, async_mode=async_mode)

    return [
        keine_loesung, gegenfragen, schrittweise, niveau,
        korrektheit, transfer, respekt,
        role_adherence,   # nativer Sokratik-Gegencheck (nutzt chatbot_role)
    ]