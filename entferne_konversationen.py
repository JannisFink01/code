# entferne_konversationen.py
# Entfernt bestimmte conversation_ids sauber aus der Konversations-JSON UND der
# Rohdaten-CSV, damit sie beim naechsten Lauf neu simuliert und neu bewertet werden.
# Legt von beiden Dateien vorher ein .bak-Backup an.
#
# Aufruf:
#   python entferne_konversationen.py <konversationen.json> <eval_rohdaten.csv> id1 id2 ...
#
# Beispiel (die 4 leeren system_prompt-Gespraeche):
#   python entferne_konversationen.py ^
#     persistence/konversationen/konversationen_system_prompt.json ^
#     persistence/csv/eval_rohdaten_system_prompt.csv ^
#     ce5e475677 31fbb6e08f 5bed2aea41 89fce0f1fe

import csv
import json
import os
import sys

csv.field_size_limit(100_000_000)  # verbose_logs kann gross sein


def entferne_aus_json(pfad, ids):
    if not os.path.exists(pfad):
        print(f"  JSON nicht gefunden: {pfad}")
        return
    data = json.load(open(pfad, encoding="utf-8"))
    vorher = len(data)
    behalten = [c for c in data if (c.get("meta") or {}).get("conversation_id") not in ids]
    os.replace(pfad, pfad + ".bak")
    json.dump(behalten, open(pfad, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"  JSON: {vorher} -> {len(behalten)} Konversationen ({vorher-len(behalten)} entfernt)")
    print(f"        Backup: {pfad}.bak")


def entferne_aus_csv(pfad, ids):
    if not os.path.exists(pfad):
        print(f"  CSV nicht gefunden: {pfad}")
        return
    with open(pfad, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)
    vorher = len(rows)
    behalten = [r for r in rows if r.get("conversation_id") not in ids]
    os.replace(pfad, pfad + ".bak")
    with open(pfad, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(behalten)
    print(f"  CSV:  {vorher} -> {len(behalten)} Zeilen ({vorher-len(behalten)} entfernt)")
    print(f"        Backup: {pfad}.bak")


def main():
    if len(sys.argv) < 4:
        print("Aufruf: python entferne_konversationen.py <konversationen.json> <eval_rohdaten.csv> id1 id2 ...")
        sys.exit(1)
    json_pfad, csv_pfad = sys.argv[1], sys.argv[2]
    ids = set(sys.argv[3:])
    print(f"Entferne {len(ids)} conversation_ids: {', '.join(sorted(ids))}")
    entferne_aus_json(json_pfad, ids)
    entferne_aus_csv(csv_pfad, ids)
    print("Fertig. Naechster Lauf simuliert + bewertet die entfernten Gespraeche neu.")


if __name__ == "__main__":
    main()