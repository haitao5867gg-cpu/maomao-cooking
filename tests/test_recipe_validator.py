import copy
import json
from pathlib import Path

import pytest

from recipe.validator import validate, validate_file

SAMPLE = Path(__file__).parent.parent / "recipe" / "samples" / "fanqie-chaodan.json"


@pytest.fixture()
def golden() -> dict:
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


def test_golden_sample_passes(golden):
    assert validate(golden) == []


def test_golden_sample_file_passes():
    assert validate_file(SAMPLE) == []


def test_missing_required_field_fails(golden):
    bad = copy.deepcopy(golden)
    del bad["sources"]
    assert any("schema" in e for e in validate(bad))


def test_single_source_fails(golden):
    bad = copy.deepcopy(golden)
    bad["sources"] = bad["sources"][:1]  # 至少 2 个来源交叉比对
    assert any("schema" in e for e in validate(bad))


def test_non_contiguous_step_order_fails(golden):
    bad = copy.deepcopy(golden)
    bad["steps"][1]["order"] = 99
    assert any("order" in e for e in validate(bad))


def test_undeclared_ingredient_fails(golden):
    bad = copy.deepcopy(golden)
    bad["steps"][0]["ingredients_used"].append("松露")
    assert any("未声明" in e for e in validate(bad))


def test_duration_mismatch_fails(golden):
    bad = copy.deepcopy(golden)
    bad["total_time_min"] = 60
    assert any("偏差" in e for e in validate(bad))


def test_invalid_unit_fails(golden):
    bad = copy.deepcopy(golden)
    bad["ingredients"][0]["unit"] = "把"
    assert any("schema" in e for e in validate(bad))
