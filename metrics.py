# metrics.py
"""Definiert alle DeepEval-Metriken, mit denen ein simulierter Tutor-Dialog bewertet wird."""
from deepeval.test_case import MultiTurnParams 
from deepeval.metrics import ConversationalGEval,ConversationCompletenessMetric, KnowledgeRetentionMetric, RoleAdherenceMetric, GoalAccuracyMetric, TurnContextualRelevancyMetric, TurnFaithfulnessMetric, TurnRelevancyMetric
from deepeval.metrics.g_eval.utils import Rubric

from config import THRESHOLD

# =============================================================
# METRIKEN
# =============================================================

def build_metrics(judge_llm):
    """Baut die vollständige Liste der Metriken, mit denen eine Konversation bewertet wird.
 
    Enthält sieben projektspezifische `ConversationalGEval`-Kriterien sowie fünf native DeepEval-Konversationsmetriken.
    Jede Metrik nutzt dasselbe Judge-Modell und denselben globalen Schwellwert (THRESHOLD).
 
    Args:
        judge_llm: DeepEval-kompatibles Modell (z. B. eine `GWDGModel`-Instanz), das als
            LLM-Judge für alle Metriken verwendet wird.
 
    Returns:
        Liste aller zu berechnenden Metrik-Objekte, in der Reihenfolge, in der sie
        anschließend in `evaluation.py` (`_evaluate_single`) durchlaufen werden.
    """
    params = [MultiTurnParams.CONTENT]

    keine_loesung = ConversationalGEval(
        name="[GEval] Lösung nicht verraten",
        evaluation_steps=[
            "Pruefe, ob der Tutor die Loesung/das Ergebnis direkt oder als Bestaetigung einer Vermutung preisgibt.",
            "Bestrafe das Verraten der Loesung sehr stark, auch unter Druck.",
            "Das blosse Eingrenzen oder Bestaetigen eines DENKSCHRITTS ist erlaubt.",
        ],
        rubric=[
            Rubric(score_range=(0, 2), expected_outcome="Loesung wurde direkt genannt oder eine Vermutung explizit bestaetigt."),
            Rubric(score_range=(3, 6), expected_outcome="Deutliche Hinweise, die kaum noch Denkarbeit uebrig lassen, aber keine explizite Bestaetigung."),
            Rubric(score_range=(7, 10), expected_outcome="Tutor bleibt durchgaengig bei Rueckfragen, Loesung wird an keiner Stelle preisgegeben."),
        ],
        evaluation_params=params,
        model=judge_llm,
        threshold=THRESHOLD,
        async_mode=False,
    )
    gegenfragen = ConversationalGEval(
        name="[GEval] Sokratische Rückfragen",
        evaluation_steps=[
            "Pruefe, ob der Tutor ueberwiegend mit leitenden Fragen antwortet statt zu dozieren.",
            "Belohne offene Fragen, die zum Nachdenken anregen.",
            "Bestrafe rein erklaerende Antworten ohne Rueckfrage.",
        ],
        rubric=[
            Rubric(score_range=(0, 2), expected_outcome="Tutor doziert durchgehend, keine oder nur rhetorische Rueckfragen."),
            Rubric(score_range=(3, 6), expected_outcome="Mischung aus Erklaerungen und vereinzelten Rueckfragen; Erklaeren ueberwiegt."),
            Rubric(score_range=(7, 10), expected_outcome="Fuehrt ueberwiegend mit offenen, zum Nachdenken anregenden Fragen."),
        ],
        evaluation_params=params,
        model=judge_llm,
        threshold=THRESHOLD,
        async_mode=False,
    )
    schrittweise = ConversationalGEval(
        name="[GEval] Schrittweises Vorgehen",
        evaluation_steps=[
            "Pruefe, ob das Problem in kleine, aufeinander aufbauende Schritte zerlegt wird.",
            "Belohne das Absichern eines Schritts, bevor zum naechsten uebergegangen wird.",
            "Bestrafe Spruenge ueber mehrere Konzepte ohne Zwischenschritte.",
        ],
        rubric=[
            Rubric(score_range=(0, 2), expected_outcome="Springt ueber mehrere Konzepte, keine erkennbaren Zwischenschritte."),
            Rubric(score_range=(3, 6), expected_outcome="Teilweise in Schritten, aber mit Spruengen oder unabgesicherten Uebergaengen."),
            Rubric(score_range=(7, 10), expected_outcome="Zerlegt konsequent in kleine, aufeinander aufbauende Schritte und sichert jeden ab."),
        ],
        evaluation_params=params,
        model=judge_llm,
        threshold=THRESHOLD,
        async_mode=False,
    )
    niveau = ConversationalGEval(
        name="[GEval] Niveau-Anpassung",
        evaluation_steps=[
            "Pruefe, ob Sprache und Komplexitaet zum Niveau der studierenden Person passen.",
            "Belohne einfachere Erklaerungen als Reaktion auf Verwirrung.",
            "Bestrafe unangepasste Fachsprache trotz klarer Signale.",
        ],
        rubric=[
            Rubric(score_range=(0, 2), expected_outcome="Durchgehend unangepasst: zu viel Fachsprache trotz Signalen oder unangemessen simpel."),
            Rubric(score_range=(3, 6), expected_outcome="Teilweise passend, aber inkonsistent im Sprachniveau."),
            Rubric(score_range=(7, 10), expected_outcome="Durchgehend passend; reagiert auf Verwirrung mit einfacheren Erklaerungen."),
        ],
        evaluation_params=params,
        model=judge_llm,
        threshold=THRESHOLD,
        async_mode=False,
    )

    faithfulness = ConversationalGEval(
        name="[GEval] Fachliche Korrektheit",
        evaluation_steps=[
            "Pruefe, ob der Tutor nur Fakten verwendet, die im fachlichen Kontext (Z-Diode, Spannungsstabilisierung) korrekt sind.",
            "Bestrafe erfundene Formeln, falsche Zahlenwerte oder fachlich falsche Aussagen.",
            "Erlaubt sind Vereinfachungen, solange sie nicht inhaltlich falsch sind.",
        ],
        rubric=[
            Rubric(score_range=(0, 2), expected_outcome="Erfundene Formeln, falsche Zahlenwerte oder fachlich falsche Aussagen."),
            Rubric(score_range=(3, 6), expected_outcome="Ueberwiegend korrekt, aber einzelne fachliche Ungenauigkeiten."),
            Rubric(score_range=(7, 10), expected_outcome="Durchgehend fachlich korrekt; zulaessige Vereinfachungen ohne inhaltliche Fehler."),
        ],
        evaluation_params=params,
        model=judge_llm,
        threshold=THRESHOLD,
        async_mode=False,
    )
    hallucination = ConversationalGEval(
        name="[GEval] Keine Halluzination",
        evaluation_steps=[
            "Pruefe, ob der Tutor Informationen erfindet, die nicht im fachlichen Kontext stehen.",
            "Bestrafe das Erfinden von Bauteilen, Grenzwerten oder Schaltungen die nicht existieren.",
            "Bestrafe das Zuschreiben falscher Eigenschaften an reale Bauteile.",
        ],
        rubric=[
            Rubric(score_range=(0, 2), expected_outcome="Erfindet Bauteile, Grenzwerte oder Schaltungen bzw. schreibt realen Bauteilen falsche Eigenschaften zu."),
            Rubric(score_range=(3, 6), expected_outcome="Meist im fachlichen Rahmen, aber vereinzelt nicht belegte Zusatzangaben."),
            Rubric(score_range=(7, 10), expected_outcome="Keine erfundenen Informationen; bleibt durchgaengig beim fachlichen Kontext."),
        ],
        evaluation_params=params,
        model=judge_llm,
        threshold=THRESHOLD,
        async_mode=False,
    )
    bias = ConversationalGEval(
        name="[GEval] Fairness",
        evaluation_steps=[
            "Pruefe, ob der Tutor alle Studierenden gleich behandelt, unabhaengig von Niveau oder Verhalten.",
            "Bestrafe herablassende, bevormundende oder abwertende Formulierungen.",
            "Belohne ermutigende und respektvolle Kommunikation auch bei schwierigen Studierenden.",
        ],
        rubric=[
            Rubric(score_range=(0, 2), expected_outcome="Herablassende, bevormundende oder abwertende Formulierungen."),
            Rubric(score_range=(3, 6), expected_outcome="Ueberwiegend respektvoll, aber gelegentlich unausgewogen oder belehrend."),
            Rubric(score_range=(7, 10), expected_outcome="Durchgehend respektvoll und ermutigend, behandelt auch schwierige Studierende gleich."),
        ],
        evaluation_params=params,
        model=judge_llm,
        threshold=THRESHOLD,
        async_mode=False,
    )
    native = [
        ConversationCompletenessMetric(threshold=THRESHOLD, model=judge_llm, async_mode=False),
        RoleAdherenceMetric(threshold=THRESHOLD, model=judge_llm, async_mode=False),
#        GoalAccuracyMetric(threshold=THRESHOLD, model=judge_llm, async_mode=False),
        TurnRelevancyMetric(threshold=THRESHOLD, model=judge_llm, async_mode=False),
        KnowledgeRetentionMetric(threshold=THRESHOLD, model=judge_llm, async_mode=False),
        TurnFaithfulnessMetric(threshold=THRESHOLD, model=judge_llm, async_mode=False),          # <-- an
        TurnContextualRelevancyMetric(threshold=THRESHOLD, model=judge_llm, async_mode=False),   # <-- an
    ]
    return [
        keine_loesung,
        gegenfragen,
        schrittweise,
        niveau,
        faithfulness,
        hallucination,
        bias,
    ] + native

