"""Turn what the team collected into files the citizens read.

Two inputs, both exported from Google as CSV into data/survey/:
- responses.csv: the Google Form. Real Bengalureans answer "what would you
  text your friend if ...". Each person is matched to a resident type, and
  their answers become example lines and slang for that type.
- field_notes.csv: one row per Reddit thread, reel or conversation the team
  read, with the take written in our own words. These become the city pulse.

Two outputs, both reviewed by a person before they are committed:
- data/voice/collected.json, merged into the voice pack by voice.load_pack.
- data/pulse/pulse.json, which voice.load_pulse prefers over the sample file.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from .voice import archetype_for

# Form question -> words its title must contain (see the team's survey doc).
QUESTIONS = {
    "consent": "18 or older",
    "age": "age group",
    "work": "what do you do",
    "money": "money",
    "rent_up": "landlord",
    "jobs_up": "new offices",
    "jobs_down": "cutting jobs",
    "cost_up": "metro fare",
    "heard": "group chat",
    "calm": "normal weekday",
    "flood": "rained",
    "phrases": "words or phrases",
    "rent_choice": "rent went up",
}
SITUATIONS = ("rent_up", "jobs_up", "jobs_down", "cost_up", "heard", "calm", "flood")
TOPICS = ("rent", "jobs", "layoffs", "cost", "traffic", "flood")

# Age group -> a typical age, keyed by the group's first number.
AGES = {18: 20, 23: 25, 28: 31, 36: 45, 55: 60}
INCOME = {"tight": "low", "manageable": "middle", "comfortable": "high"}
# "What do you do?" answer -> (sector, job) in the persona vocabulary. First match wins.
WORK = [
    (("driver",), ("services", "auto driver")),
    (("darshini", "business"), ("retail", "kirana shop owner")),
    (("factory", "construction"), ("manufacturing", "machine operator")),
    (("it or tech",), ("it", "software engineer")),
    (("student",), ("services", "student")),
    (("retired", "homemaker"), ("services", "retired")),
]

MAX_CHARS = 220
_PRIVATE = [
    re.compile(r"\S+@\S+\.\S+"),  # emails
    re.compile(r"https?://\S+|www\.\S+"),  # links
    re.compile(r"(?:\+?91[\s-]?)?(?:\d[\s-]?){10}"),  # phone numbers
    re.compile(r"(?<!\w)@\w+"),  # @handles
    re.compile(r"\bu/\w+"),  # reddit usernames
]


def clean(text: str) -> str:
    """Strip anything that could identify someone, tidy spacing, cap the length."""
    for pattern in _PRIVATE:
        text = pattern.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > MAX_CHARS:
        text = text[: MAX_CHARS - 1].rsplit(" ", 1)[0] + "…"
    return text if len(text) >= 8 else ""


def respondent(row: dict, cols: dict) -> SimpleNamespace:
    """A persona-shaped stand-in, so archetype_for can match form answers."""
    first = re.match(r"\d+", row.get(cols.get("age", ""), "") or "")
    age = AGES.get(int(first.group()), 30) if first else 30
    money = (row.get(cols.get("money", ""), "") or "").strip().lower()
    work = (row.get(cols.get("work", ""), "") or "").lower()
    sector, job = next((sj for words, sj in WORK if any(w in work for w in words)), ("services", "service worker"))
    return SimpleNamespace(age=age, sector=sector, job=job, income_band=INCOME.get(money, "middle"))


def find_columns(header: list[str]) -> dict:
    """Map each question key to the export column whose title contains its words."""
    cols = {}
    for key, words in QUESTIONS.items():
        match = next((h for h in header if words in h.lower()), None)
        if match:
            cols[key] = match
    return cols


def _phrases(text: str) -> list[str]:
    out = []
    for p in (text or "").split(","):
        p = re.sub(r"\s+", " ", p).strip(" .\"'")
        if 2 <= len(p) <= 30 and len(p.split()) <= 4 and not any(pat.search(p) for pat in _PRIVATE):
            out.append(p)
    return out


def build_voice(rows: list[dict], header: list[str], notes: list[dict], pack: dict) -> tuple[dict, dict]:
    """Form rows + field notes -> (collected voice, summary for the console)."""
    cols = find_columns(header)
    if rows and "consent" not in cols:
        raise ValueError('The form export has no consent column. Add question 1 ("I\'m 18 or older ...").')
    labels = {a.get("label", a["id"]).lower(): a["id"] for a in pack["archetypes"]}
    voice: dict = {}
    phrase_counts: dict[str, Counter] = {}
    choices: Counter = Counter()
    kept = 0
    for row in rows:
        if "yes" not in (row.get(cols["consent"]) or "").lower():
            continue
        kept += 1
        archetype = archetype_for(respondent(row, cols), pack)
        if not archetype:
            continue
        entry = voice.setdefault(archetype["id"], {"examples": {}, "phrases": []})
        for s in SITUATIONS:
            line = clean(row.get(cols.get(s, ""), "") or "")
            if line and line not in entry["examples"].get(s, []):
                entry["examples"].setdefault(s, []).append(line)
        phrase_counts.setdefault(archetype["id"], Counter()).update(_phrases(row.get(cols.get("phrases", ""), "")))
        if row.get(cols.get("rent_choice", "")):
            choices[row[cols["rent_choice"]].strip()] += 1

    for note in notes:
        aid = labels.get((note.get("resident_type") or "").strip().lower())
        if aid:
            voice.setdefault(aid, {"examples": {}, "phrases": []})
            phrase_counts.setdefault(aid, Counter()).update(_phrases(note.get("phrases", "")))
    for aid, counts in phrase_counts.items():
        voice[aid]["phrases"] = [p for p, _ in counts.most_common(12)]

    collected = {
        "_note": "Built by scripts/build_voice.py from the team's Google Form and field notes. "
                 "Anonymous real answers: a teammate reads every line before this file is committed.",
        "built": date.today().isoformat(),
        "responses": kept,
        "archetypes": voice,
    }
    summary = {"responses": len(rows), "kept": kept, "rent_choice": dict(choices.most_common()),
               "lines": {aid: sum(map(len, v["examples"].values())) for aid, v in voice.items()}}
    return collected, summary


def build_pulse(notes: list[dict], sample: dict) -> tuple[dict, dict]:
    """Field notes -> city pulse. Topics with no notes yet keep the sample takes."""
    topics: dict[str, list[str]] = {}
    skipped = 0
    for note in notes:
        topic = (note.get("topic") or "").strip().lower()
        take = clean(note.get("take") or "")
        if topic not in TOPICS or not take:
            skipped += 1
            continue
        if take not in topics.setdefault(topic, []):
            topics[topic].append(take)
    from_notes = {t: len(v) for t, v in topics.items()}
    for topic, takes in sample.get("topics", {}).items():
        topics.setdefault(topic, takes)
    pulse = {
        "_note": "Built by scripts/build_voice.py. Takes are the team's own words after reading Reddit, Instagram "
                 "and real conversations; no usernames, nothing copied. Topics without notes keep the sample takes.",
        "source": "team field notes",
        "built": date.today().isoformat(),
        "topics": topics,
    }
    return pulse, {"notes": len(notes), "skipped": skipped, "per_topic": from_notes}


def read_csv(path: Path) -> tuple[list[str], list[dict]]:
    if not path.exists():
        return [], []
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        return list(reader.fieldnames or []), rows


def run(data_dir: Path) -> dict:
    """Read data/survey/*.csv, write collected.json and pulse.json, return a summary."""
    survey = data_dir / "survey"
    header, rows = read_csv(survey / "responses.csv")
    _, notes = read_csv(survey / "field_notes.csv")
    if not rows and not notes:
        raise FileNotFoundError(f"Nothing to build: put responses.csv and/or field_notes.csv in {survey}")
    pack = json.loads((data_dir / "voice" / "voice_pack.json").read_text())
    summary: dict = {}
    if rows or any(n.get("phrases") for n in notes):
        collected, summary["voice"] = build_voice(rows, header, notes, pack)
        (data_dir / "voice" / "collected.json").write_text(json.dumps(collected, indent=2, ensure_ascii=False) + "\n")
    if notes:
        sample = json.loads((data_dir / "pulse" / "pulse.sample.json").read_text())
        pulse, summary["pulse"] = build_pulse(notes, sample)
        (data_dir / "pulse" / "pulse.json").write_text(json.dumps(pulse, indent=2, ensure_ascii=False) + "\n")
    return summary
