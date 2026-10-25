"""Build the citizens' Bengaluru voice from what the team collected.

Put the Google exports in backend/data/survey/:
  responses.csv    the Google Form responses (Responses > Sheets > Download CSV)
  field_notes.csv  the team's field notes sheet

Then:
  python scripts/build_voice.py

It writes data/voice/collected.json and data/pulse/pulse.json. Read both
before committing: delete anything abusive, anything that names a person, and
anything about caste, religion or language.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from namma.agents.voice_build import run  # noqa: E402
from namma.config import Settings  # noqa: E402


def main() -> None:
    try:
        summary = run(Settings().data_dir)
    except (FileNotFoundError, ValueError) as e:
        sys.exit(str(e))
    if "voice" in summary:
        v = summary["voice"]
        print(f"Form: {v['kept']} of {v['responses']} responses kept (the rest had no 18+ tick)")
        for aid, n in sorted(v["lines"].items(), key=lambda kv: -kv[1]):
            print(f"  {aid:16} {n} lines")
        if v["rent_choice"]:
            total = sum(v["rent_choice"].values())
            print("If rent went up 20%:")
            for choice, n in v["rent_choice"].items():
                print(f"  {choice:34} {n:4}  {100 * n / total:.0f}%")
        print("Wrote data/voice/collected.json")
    if "pulse" in summary:
        p = summary["pulse"]
        print(f"Field notes: {p['notes']} read, {p['skipped']} skipped (unknown topic or empty take)")
        for topic, n in p["per_topic"].items():
            print(f"  {topic:10} {n} takes")
        print("Wrote data/pulse/pulse.json")
    print("Now read both files before committing.")


if __name__ == "__main__":
    main()
