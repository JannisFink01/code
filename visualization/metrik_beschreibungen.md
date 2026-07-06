
# Metrik-Beschreibungen: Evaluation des virtuellen Tutors

## GEval-Metriken [CGE]
GEval-Metriken sind kriterienbasierte Bewertungen – ein LLM bewertet die
Tutor-Antworten anhand vorgegebener Kriterien (Score 0–1). Die Kriterien
sind spezifisch auf sokratisches Tutor-Verhalten im Kontext
Elektronik/Elektrotechnik ausgerichtet.

| Metrik | Was sie misst | Belohnt | Bestraft |
|---|---|---|---|
| [CGE] Keine Lösung | Ob der Tutor die Lösung zurückhält – auch unter Druck | Eingrenzung von Denkschritten | Direktes Verraten oder Bestätigen der Lösung |
| [CGE] Gegenfragen | Ob der Tutor überwiegend mit leitenden Fragen antwortet | Offene, zum Nachdenken anregende Fragen | Rein erklärende Antworten ohne Rückfrage |
| [CGE] Schrittweise | Ob das Problem in aufeinander aufbauende Schritte zerlegt wird | Absichern eines Schritts vor dem nächsten | Sprünge über mehrere Konzepte ohne Zwischenschritte |
| [CGE] Niveau | Ob Sprache und Komplexität zum Kenntnisstand der Studierenden passen | Vereinfachung als Reaktion auf Verwirrung | Unangepasste Fachsprache trotz klarer Signale |
| [CGE] Faithfulness | Ob nur fachlich korrekte Fakten verwendet werden (Z-Diode, Spannungsstabilisierung) | Zulässige Vereinfachungen | Erfundene Formeln, falsche Zahlenwerte, fachlich falsche Aussagen |
| [CGE] Hallucination | Ob der Tutor Informationen erfindet | – | Erfundene Bauteile/Grenzwerte; falsch zugeschriebene Eigenschaften |
| [CGE] Bias | Ob alle Studierenden gleich behandelt werden | Ermutigende, respektvolle Kommunikation | Herablassende oder abwertende Formulierungen |

## Standard-Metriken
Strukturell definierte Bewertungen über den gesamten Dialogverlauf.

| Metrik | Was sie misst |
|---|---|
| Conversation Completeness | Werden alle relevanten Aspekte vollständig beantwortet? |
| Role Adherence | Hält der Tutor seine Rolle konsequent ein? |
| Goal Accuracy | Wird das Lernziel im Gespräch erreicht? |
| Turn Relevancy | Sind Antworten relevant zur jeweiligen Studierenden-Aussage? |
| Knowledge Retention | Greift der Tutor auf früheres Gesprächswissen zurück? |
