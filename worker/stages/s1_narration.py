"""Stage 1: recipe.json → narration.json（确定性模板版）。

铁律：所有用量/火候/时长逐字来自 recipe.json。
本版本用模板生成，保证零幻觉；LLM 润色版后续接 llm/gateway，
但其输出仍须通过 s5_qc 的一致性检查。
幂等：输出已存在则跳过（--force 覆盖）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

CHARS_PER_SEC = 5.2  # 中文旁白语速估算（TTS 提速 15% 后）


def _ingredient_text(ing: dict) -> str:
    if ing["unit"] == "适量":
        return f"{ing['name']}适量"
    amt = ing["amount"]
    amt = int(amt) if amt == int(amt) else amt
    return f"{ing['name']}{amt}{ing['unit']}"


def build_narration(recipe: dict) -> list[dict]:
    scenes: list[dict] = []
    name = recipe["name"]

    scenes.append({
        "scene": "hook",
        "narration": f"今天猫猫教你做{name}，跟着做零失败，喵！",
        "screen_text": name,
    })

    ing_list = "、".join(_ingredient_text(i) for i in recipe["ingredients"])
    scenes.append({
        "scene": "ingredients",
        "narration": f"先准备食材：{ing_list}。",
        "screen_text": "  ".join(_ingredient_text(i) for i in recipe["ingredients"]),
    })

    for s in recipe["steps"]:
        bar = []
        if s.get("heat") and s["heat"] != "无":
            bar.append(f"火候：{s['heat']}")
        secs = int(s["duration_sec"])
        bar.append(f"约{secs}秒" if secs < 60 else f"约{secs // 60}分{secs % 60 or ''}{'秒' if secs % 60 else '钟'}")
        if s.get("visual_cue"):
            bar.append(f"✓ {s['visual_cue']}")
        scenes.append({
            "scene": f"step_{s['order']}",
            "narration": f"{s['action']}。",
            "screen_text": " ｜ ".join(bar),
        })

    tip = f"小提示：{recipe['tips'][0]}。" if recipe.get("tips") else ""
    scenes.append({
        "scene": "outro",
        "narration": f"香喷喷的{name}就做好了！{tip}关注猫猫，天天学做菜！",
        "screen_text": f"{name} · 完整用料见简介",
    })

    for sc in scenes:
        sc["est_duration_sec"] = round(len(sc["narration"]) / CHARS_PER_SEC, 1)
    return scenes


def run(recipe_path: str | Path, workdir: str | Path, force: bool = False) -> Path:
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    out = workdir / "narration.json"
    if out.exists() and not force:
        return out
    recipe = json.loads(Path(recipe_path).read_text(encoding="utf-8"))
    out.write_text(json.dumps(build_narration(recipe), ensure_ascii=False, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    print(run(sys.argv[1], sys.argv[2], force="--force" in sys.argv))
