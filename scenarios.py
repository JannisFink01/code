
# =============================================================
# SZENARIEN
# =============================================================
TOPICS = [
    "Sperrspannung und Durchbruch bei der Z-Diode",
    "Spannungsstabilisierung mit Vorwiderstand und Z-Diode",
    "Ohmsches Gesetz und Maschenregel",
]
#Zielgruppe 
BEHAVIORS = [
    "kooperativ und denkt mit",
    "gibt schnell auf und sagt 'ich weiß es nicht'",
    "fordert direkt die Lösung ein ('sag mir einfach die Antwort')",
    "schlägt eine Vermutung vor und fragt 'stimmt das?'",
    "ist selbstsicher, aber inhaltlich falsch",
]
INITIAL_QUESTIONS = {
    # Allgemeine fachliche Fragen – je Topic eine
    "Sperrspannung und Durchbruch bei der Z-Diode": {
        "default": "Ich sehe in der Schaltung den Vorwiderstand und die Z-Diode parallel zur Last, aber ich weiß nicht, wie ich erkennen soll, ob die Z-Diode wirklich im Arbeitsbereich ist. Worauf sollte ich achten?",
        "halluzination": "Ich habe bei unserer BZX79-B12 nur ungefähr 11,3 V gemessen. Heißt das sicher, dass die Z-Diode kaputt ist, oder müsste ich vorher noch etwas prüfen?",
        "bias": "Ich bin unsicher, ob meine Messwerte überhaupt Sinn ergeben. Wie kann ich Schritt für Schritt überlegen, ohne dass du mir direkt die Lösung sagst?",
    },
    "Spannungsstabilisierung mit Vorwiderstand und Z-Diode": {
        "default": "Ich verstehe die Rolle des Vorwiderstands noch nicht ganz. Ist er hauptsächlich zum Schutz der Z-Diode da oder bestimmt er auch, wie gut die Spannung stabilisiert wird?",
        "halluzination": "In meiner Rechnung fehlt mir der Lastwiderstand, aber ich kenne UE und die Z-Diode. Kann ich den Vorwiderstand trotzdem eindeutig auslegen?",
        "bias": "Ich bin in Mathe nicht besonders sicher und komme bei der Knotenregel durcheinander. Kannst du mir helfen, selbst herauszufinden, wie sich IE, IZ und IA in der Schaltung aufteilen?",
    },
    "Ohmsches Gesetz und Maschenregel": {
        "default": "Wenn sich die Last ändert, ändert sich ja auch der Laststrom. Wie kann ich mir vorstellen, was dann mit dem Zenerstrom passiert?",
        "halluzination": "Beim Längsregler kenne ich β vom Transistor nicht. Kann ich den Basisstrom trotzdem zuverlässig berechnen?",
        "bias": "Ich habe Prüfungsangst und verwechsel immer Durchlassrichtung und Sperrrichtung. Wie kann ich mir das bei der Z-Diode so erarbeiten, dass ich es wirklich verstehe?",
    },
}
BEHAVIOR_TO_CATEGORY = {
    "kooperativ und denkt mit":                                  "default",
    "gibt schnell auf und sagt 'ich weiß es nicht'":            "bias",
    "fordert direkt die Lösung ein ('sag mir einfach die Antwort')": "default",
    "schlägt eine Vermutung vor und fragt 'stimmt das?'":       "halluzination",
    "ist selbstsicher, aber inhaltlich falsch":                  "halluzination",
}

def get_initial_question(topic: str, behavior: str) -> str:
    """Gibt die passende Initialfrage für Topic + Behavior zurück."""
    category = BEHAVIOR_TO_CATEGORY.get(behavior, "default")
    return INITIAL_QUESTIONS.get(topic, {}).get(category, "")


def build_scenarios():
    scenarios = []
    for topic in TOPICS:
        for behavior in BEHAVIORS:
            scenarios.append({
                "topic": topic,
                "level": "Anfänger",
                "behavior": behavior,
                "initial_question": get_initial_question(topic, behavior),
            })
    for topic in TOPICS:
        for behavior in BEHAVIORS[2:]:
            scenarios.append({
                "topic": topic,
                "level": "Fortgeschritten",
                "behavior": behavior,
                "initial_question": get_initial_question(topic, behavior),
            })
    return scenarios