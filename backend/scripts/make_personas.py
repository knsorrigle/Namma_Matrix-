"""Generate the sample citizens file (backend/data/citizens.sample.json).

A placeholder until BABU builds personas from real ward demographics. Names
use a first name and an initial only, so no surname hints at caste or
community. Run:  python scripts/make_personas.py
"""

from __future__ import annotations

import json
import random
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
PER_WARD = 5
SEED = 7

NAMES = {
    "Kannada": [("Lakshmi", "F"), ("Manjunath", "M"), ("Kavya", "F"), ("Prakash", "M"), ("Shwetha", "F"),
                ("Raghavendra", "M"), ("Divya", "F"), ("Santosh", "M"), ("Bhavya", "F"), ("Girish", "M"),
                ("Nandini", "F"), ("Chethan", "M"), ("Sowmya", "F"), ("Harish", "M"), ("Rekha", "F"), ("Darshan", "M")],
    "Tamil": [("Karthik", "M"), ("Priya", "F"), ("Senthil", "M"), ("Meena", "F"), ("Arun", "M"), ("Deepa", "F"), ("Vignesh", "M")],
    "Telugu": [("Srinivas", "M"), ("Swathi", "F"), ("Ravi", "M"), ("Anusha", "F"), ("Harika", "F"), ("Naveen", "M")],
    "Hindi": [("Rahul", "M"), ("Neha", "F"), ("Vikas", "M"), ("Anjali", "F")],
    "Malayalam": [("Anoop", "M"), ("Reshma", "F"), ("Vishnu", "M"), ("Athira", "F")],
    "Marathi": [("Sachin", "M"), ("Snehal", "F")],
    "Bengali": [("Arijit", "M"), ("Moumita", "F")],
}
LANG_WEIGHTS = {"Kannada": 40, "Tamil": 15, "Telugu": 14, "Hindi": 13, "Malayalam": 9, "Marathi": 5, "Bengali": 4}

# job: (sector, income band, min age, max age)
JOBS = {
    "software engineer": ("it", "high", 23, 40),
    "QA tester": ("it", "middle", 22, 35),
    "data analyst": ("it", "middle", 23, 38),
    "IT project manager": ("it", "high", 32, 52),
    "night-shift support engineer": ("it", "middle", 22, 32),
    "machine operator": ("manufacturing", "low", 20, 55),
    "factory supervisor": ("manufacturing", "middle", 30, 58),
    "auto driver": ("services", "low", 22, 62),
    "delivery rider": ("services", "low", 19, 35),
    "nurse": ("services", "middle", 23, 55),
    "school teacher": ("services", "middle", 25, 58),
    "darshini owner": ("services", "middle", 30, 65),
    "security guard": ("services", "low", 21, 60),
    "bank clerk": ("services", "middle", 24, 58),
    "domestic worker": ("services", "low", 20, 60),
    "kirana shop owner": ("retail", "middle", 28, 68),
    "mall sales associate": ("retail", "low", 19, 30),
    "vegetable vendor": ("retail", "low", 25, 65),
    "mason": ("construction", "low", 20, 55),
    "site engineer": ("construction", "middle", 23, 45),
}
FAMILY = ["lives alone", "shares a flat with two friends", "married, one child", "married, two children",
          "lives with elderly parents", "newly married", "single parent of a teenager", "lives with spouse, children grown up"]
VALUES = ["family first", "career growth", "saving money", "community", "tradition", "independence",
          "children's education", "clean environment", "stability", "a good work-life balance"]
TRAITS = ["anxious", "optimistic", "stubborn", "curious", "frugal", "outspoken", "quiet", "ambitious", "sociable", "sceptical"]


def main() -> None:
    rng = random.Random(SEED)
    wards = json.loads((DATA / "wards.sample.json").read_text())["wards"]
    used: set[str] = set()
    citizens = []
    for ward in wards:
        sectors = list(ward["jobs"])
        weights = [ward["jobs"][s] for s in sectors]
        for i in range(PER_WARD):
            sector = rng.choices(sectors, weights)[0] if i < 3 else rng.choice(sectors)
            taken = {c["job"] for c in citizens if c["ward_id"] == ward["id"]}
            job = rng.choice([j for j, v in JOBS.items() if v[0] == sector and j not in taken]
                             or [j for j, v in JOBS.items() if v[0] == sector])
            _, band, lo, hi = JOBS[job]
            lang = rng.choices(list(LANG_WEIGHTS), list(LANG_WEIGHTS.values()))[0]
            options = [n for n in NAMES[lang] if n[0] not in used] or NAMES[lang]
            first, gender = rng.choice(options)
            used.add(first)
            age = rng.randint(lo, hi)
            family = rng.choice(FAMILY)
            values = rng.sample(VALUES, 2)
            traits = rng.sample(TRAITS, 2)
            metro = sector in ("it", "services") and rng.random() < 0.45
            cid = f"c{len(citizens) + 1:02d}"
            citizens.append({
                "id": cid,
                "name": f"{first} {chr(65 + rng.randrange(26))}.",
                "age": age,
                "gender": gender,
                "ward_id": ward["id"],
                "job": job,
                "sector": sector,
                "income_band": band,
                "language": lang,
                "family": family,
                "values": values,
                "traits": traits,
                "commutes_by_metro": metro,
                "bio": f"{age}-year-old {job} in {ward['name']}, {family}. Speaks {lang} at home. "
                       f"Cares about {values[0]} and {values[1]}; {traits[0]} and {traits[1]}.",
            })
    out = {"_note": "PLACEHOLDER personas from scripts/make_personas.py. BABU replaces these with personas built from ward demographics.",
           "citizens": citizens}
    (DATA / "citizens.sample.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {len(citizens)} citizens")


if __name__ == "__main__":
    main()
