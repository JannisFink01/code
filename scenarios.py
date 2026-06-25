
# =============================================================
# SZENARIEN
# =============================================================
# Hier werden die Gesprächsszenarien erstellt die in der Evaluierung durchgespielt werden. Jedes Szenario besteht aus einem Thema, dem Niveau der Studierenden und deren Verhalten. 
TOPICS = [
    "Sperrspannung und Durchbruch bei der Z-Diode",
    "Spannungsstabilisierung mit Vorwiderstand und Z-Diode",
    "Ohmsches Gesetz und Maschenregel",
]

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
            scenarios.append(
                {"topic": topic, "level": "Anfänger", "behavior": behavior}
            )
    for topic in TOPICS:
        for behavior in BEHAVIORS[2:]:
            scenarios.append(
                {"topic": topic, "level": "Fortgeschritten", "behavior": behavior}
            )
    return scenarios
