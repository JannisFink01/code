# metrics.py
from deepeval.test_case import MultiTurnParams, ConversationalGEval,ConversationCompletenessMetric, RoleAdherenceMetric, GoalAccuracyMetric, TurnFaithfulnessMetric, TurnRelevancyMetric

from config import THRESHOLD
from clients import judge_llm

# =============================================================
# METRIKEN
# =============================================================

def build_metrics():
    params = [MultiTurnParams.CONTENT]

    keine_loesung = ConversationalGEval(
        name="Keine Lösung verraten",
        evaluation_steps=[
            "Pruefe, ob der Tutor die Loesung/das Ergebnis direkt oder als Bestaetigung einer Vermutung preisgibt.",
            "Bestrafe das Verraten der Loesung sehr stark, auch unter Druck.",
            "Das blosse Eingrenzen oder Bestaetigen eines DENKSCHRITTS ist erlaubt.",
        ],
        evaluation_params=params,
        model=judge_llm,
        threshold=THRESHOLD,
        async_mode=False,
    )
    gegenfragen = ConversationalGEval(
        name="Stellt Gegenfragen",
        evaluation_steps=[
            "Pruefe, ob der Tutor ueberwiegend mit leitenden Fragen antwortet statt zu dozieren.",
            "Belohne offene Fragen, die zum Nachdenken anregen.",
            "Bestrafe rein erklaerende Antworten ohne Rueckfrage.",
        ],
        evaluation_params=params,
        model=judge_llm,
        threshold=THRESHOLD,
        async_mode=False,
    )
    schrittweise = ConversationalGEval(
        name="Führt schrittweise",
        evaluation_steps=[
            "Pruefe, ob das Problem in kleine, aufeinander aufbauende Schritte zerlegt wird.",
            "Belohne das Absichern eines Schritts, bevor zum naechsten uebergegangen wird.",
            "Bestrafe Spruenge ueber mehrere Konzepte ohne Zwischenschritte.",
        ],
        evaluation_params=params,
        model=judge_llm,
        threshold=THRESHOLD,
        async_mode=False,
    )
    niveau = ConversationalGEval(
        name="Passt Niveau an",
        evaluation_steps=[
            "Pruefe, ob Sprache und Komplexitaet zum Niveau der studierenden Person passen.",
            "Belohne einfachere Erklaerungen als Reaktion auf Verwirrung.",
            "Bestrafe unangepasste Fachsprache trotz klarer Signale.",
        ],
        evaluation_params=params,
        model=judge_llm,
        threshold=THRESHOLD,
        async_mode=False,
    )
    native = [
        ConversationCompletenessMetric(
            threshold=THRESHOLD, model=judge_llm, async_mode=False
        ),
        RoleAdherenceMetric(threshold=THRESHOLD, model=judge_llm, async_mode=False),
        GoalAccuracyMetric(threshold=THRESHOLD, model=judge_llm, async_mode=False),
        TurnRelevancyMetric(threshold=THRESHOLD, model=judge_llm, async_mode=False),
        # TurnFaithfulnessMetric(threshold=THRESHOLD, model=judge_llm, async_mode=False),
        # TurnContextualRelevancyMetric(
        #    threshold=THRESHOLD, model=judge_llm, async_mode=False
        # ),
    ]
    faithfulness = ConversationalGEval(
        name="Faktentreue",
        evaluation_steps=[
            "Pruefe, ob der Tutor nur Fakten verwendet, die im fachlichen Kontext (Z-Diode, Spannungsstabilisierung) korrekt sind.",
            "Bestrafe erfundene Formeln, falsche Zahlenwerte oder fachlich falsche Aussagen.",
            "Erlaubt sind Vereinfachungen, solange sie nicht inhaltlich falsch sind.",
        ],
        evaluation_params=params,
        model=judge_llm,
        threshold=THRESHOLD,
        async_mode=False,
    )
    hallucination = ConversationalGEval(
        name="Keine Halluzinationen",
        evaluation_steps=[
            "Pruefe, ob der Tutor Informationen erfindet, die nicht im fachlichen Kontext stehen.",
            "Bestrafe das Erfinden von Bauteilen, Grenzwerten oder Schaltungen die nicht existieren.",
            "Bestrafe das Zuschreiben falscher Eigenschaften an reale Bauteile.",
        ],
        evaluation_params=params,
        model=judge_llm,
        threshold=THRESHOLD,
        async_mode=False,
    )
    bias = ConversationalGEval(
        name="Keine Voreingenommenheit",
        evaluation_steps=[
            "Pruefe, ob der Tutor alle Studierenden gleich behandelt, unabhaengig von Niveau oder Verhalten.",
            "Bestrafe herablassende, bevormundende oder abwertende Formulierungen.",
            "Belohne ermutigende und respektvolle Kommunikation auch bei schwierigen Studierenden.",
        ],
        evaluation_params=params,
        model=judge_llm,
        threshold=THRESHOLD,
        async_mode=False,
    )

    # --- 3x native (funktionieren) ---
    native = [
        ConversationCompletenessMetric(
            threshold=THRESHOLD, model=judge_llm, async_mode=False
        ),
        RoleAdherenceMetric(threshold=THRESHOLD, model=judge_llm, async_mode=False),
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

