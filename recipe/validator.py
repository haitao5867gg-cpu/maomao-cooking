"""菜谱校验器 — recipe.json 入内容日历前的强制关卡。

schema 校验之外的业务规则：
1. 步骤 order 连续且从 1 开始
2. steps 中引用的食材必须在 ingredients 里声明
3. 步骤总时长与 total_time_min 偏差 ≤ 30%
4. '适量'单位的食材占比 ≤ 20%（保证可还原性）
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

SCHEMA_PATH = Path(__file__).parent / "schema" / "recipe.schema.json"


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate(recipe: dict) -> list[str]:
    """返回错误列表，空列表 = 通过。"""
    errors: list[str] = []

    try:
        jsonschema.validate(recipe, load_schema())
    except jsonschema.ValidationError as e:
        return [f"schema: {e.message}"]

    steps = recipe["steps"]
    orders = [s["order"] for s in steps]
    if orders != list(range(1, len(steps) + 1)):
        errors.append(f"步骤 order 必须为 1..{len(steps)} 连续，实际 {orders}")

    declared = {i["name"] for i in recipe["ingredients"]}
    for s in steps:
        for name in s.get("ingredients_used", []):
            if name not in declared:
                errors.append(f"步骤 {s['order']} 引用了未声明的食材：{name}")

    steps_total_min = sum(s["duration_sec"] for s in steps) / 60
    declared_min = recipe["total_time_min"]
    if abs(steps_total_min - declared_min) > declared_min * 0.3:
        errors.append(
            f"步骤总时长 {steps_total_min:.1f}min 与声明 {declared_min}min 偏差超 30%"
        )

    vague = [i["name"] for i in recipe["ingredients"] if i["unit"] == "适量"]
    if len(vague) > len(recipe["ingredients"]) * 0.2:
        errors.append(f"'适量'食材过多（{vague}），影响可还原性")

    return errors


def validate_file(path: str | Path) -> list[str]:
    return validate(json.loads(Path(path).read_text(encoding="utf-8")))
