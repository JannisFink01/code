# dialog_kompakt.py
# Kompakte Darstellung der Konversationen: pro Gespraech nur eine knappe Ueberschrift
# (Thema · Verhalten · Niveau) und darunter der reine Nachrichtenaustausch User/Assistant.
#
# Aufruf:
#   python dialog_kompakt.py konversationen_system_prompt.json
#   -> erzeugt konversationen_system_prompt_dialoge.md
# optional Zielpfad:
#   python dialog_kompakt.py <eingabe.json> <ausgabe.md>

import json
import sys
import os


def bereinige(text: str) -> str:
    """Schneidet angehaengten Quellen-/Token-/Marker-Block ab und macht <br> zu Umbruch."""
    if not text:
        return ""
    for trenner in ("<br><!-- qdrant", "<!-- qdrant", "\nQuellen:", "\nToken:"):
        i = text.find(trenner)
        if i != -1:
            text = text[:i]
    return text.replace("<br>", "\n").strip()


def main():
    if len(sys.argv) < 2:
        print("Aufruf: python dialog_kompakt.py <konversationen.json> [ausgabe.md]")
        sys.exit(1)

    eingabe = sys.argv[1]
    ausgabe = sys.argv[2] if len(sys.argv) > 2 else eingabe.rsplit(".", 1)[0] + "_dialoge.md"

    data = json.load(open(eingabe, encoding="utf-8"))
    out = []

    for c in data:
        m = c.get("meta") or {}
        cid = m.get("conversation_id", "")
        # knappe Ueberschrift: ID zuerst, dann Thema · Verhalten · Niveau
        rest = " · ".join(
            x for x in (m.get("topic"), m.get("behavior"), m.get("level")) if x
        )
        out.append(f"## [{cid}] {rest}\n")

        for t in c.get("turns", []):
            role = t.get("role")
            if role == "system":
                continue
            wer = "User" if role == "user" else "Assistant"
            inhalt = t.get("content", "")
            if role == "assistant":
                inhalt = bereinige(inhalt)
            out.append(f"**{wer}:** {inhalt}\n")

        out.append("\n---\n")  # Trenner zwischen Gespraechen

    with open(ausgabe, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print(f"{len(data)} Gespräche -> {ausgabe}")


if __name__ == "__main__":
    main()