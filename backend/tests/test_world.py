import pytest
from pydantic import ValidationError

from namma.config import Settings
from namma.contracts import WorldChange
from namma.world import WorldEngine


def make_world():
    return WorldEngine.from_file(Settings().data_dir / "wards.sample.json")


def test_contract_rejects_ward_metric_on_city():
    with pytest.raises(ValidationError):
        WorldChange(target="city", metric="rent", op="mul", value=1.1)


def test_more_jobs_push_rent_up_gradually():
    world = make_world()
    start = world.wards["whitefield"].rent
    world.apply_change(WorldChange(target="whitefield", metric="jobs.it", op="mul", value=1.3))
    world.step()
    after_one = world.wards["whitefield"].rent
    for _ in range(10):
        world.step()
    assert start < after_one < world.wards["whitefield"].rent
    assert world.wards["malleshwaram"].rent == pytest.approx(19000, rel=0.01)


def test_corporate_tax_shrinks_it_jobs():
    world = make_world()
    before = world.wards["electronic_city"].jobs["it"]
    world.apply_change(WorldChange(target="city", metric="corporate_tax", op="add", value=10))
    for _ in range(10):
        world.step()
    assert world.wards["electronic_city"].jobs["it"] < before


def test_migration_moves_people():
    world = make_world()
    world.migrate("koramangala", "yelahanka", 100)
    assert world.wards["koramangala"].population == 60900
    assert world.wards["yelahanka"].population == 47100
