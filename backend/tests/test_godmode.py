from namma.config import Settings
from namma.godmode import parse_rules
from namma.world import WorldEngine

WARDS = list(WorldEngine.from_file(Settings().data_dir / "wards.sample.json").wards.values())


def changes(text):
    return {(c.target, c.metric, c.op, c.value) for c in parse_rules(text, WARDS).changes}


def test_demo_command():
    got = changes("Three big MNCs open in Whitefield, but the government adds a heavy tax on them.")
    assert ("whitefield", "jobs.it", "mul", 1.15) in got
    assert ("city", "corporate_tax", "add", 8) in got


def test_metro_fare_percent():
    assert changes("Metro fare goes up by 25%") == {("city", "metro_fare", "mul", 1.25)}


def test_layoffs():
    got = changes("Two IT companies shut down offices in Electronic City")
    assert got == {("electronic_city", "jobs.it", "mul", 0.9)}


def test_rent_cap_in_two_wards():
    got = changes("Rent control in Koramangala and Malleshwaram")
    assert got == {("koramangala", "rent", "mul", 0.95), ("malleshwaram", "rent", "mul", 0.95)}


def test_unknown_command_warns():
    result = parse_rules("Make everyone happy", WARDS)
    assert not result.changes and result.warnings
