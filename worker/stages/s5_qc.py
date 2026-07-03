"""Stage 5: 质检。ffprobe 技术检查 + 菜谱一致性 diff。

技术检查：分辨率 1080x1920、总时长 <60s、含音轨。
一致性检查（还原度的最后一道闸）：
  recipe.json 每个食材的"名称+用量"必须出现在某个场景的
  narration 或 screen_text 里，逐项 diff，缺一即 fail。
输出 qc_report.json；fail 时退出码 1，上传 stage 不会执行。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def probe(video: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", "-show_format", str(video)],
        capture_output=True, text=True, check=True,
    )
    return json.loads(out.stdout)


def _amount_str(ing: dict) -> str:
    amt = ing["amount"]
    amt = int(amt) if amt == int(amt) else amt
    return f"{ing['name']}{amt}{ing['unit']}" if ing["unit"] != "适量" else f"{ing['name']}适量"


def run(recipe_path: str | Path, workdir: str | Path) -> dict:
    workdir = Path(workdir)
    recipe = json.loads(Path(recipe_path).read_text(encoding="utf-8"))
    scenes = json.loads((workdir / "narration.json").read_text(encoding="utf-8"))
    video = workdir / "final.mp4"
    report: dict = {"checks": {}, "pass": True}

    info = probe(video)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    has_audio = any(s["codec_type"] == "audio" for s in info["streams"])
    duration = float(info["format"]["duration"])
    report["checks"]["resolution"] = {"ok": (v["width"], v["height"]) == (1080, 1920), "actual": f"{v['width']}x{v['height']}"}
    report["checks"]["duration_under_60s"] = {"ok": duration < 60, "actual": round(duration, 1)}
    report["checks"]["has_audio"] = {"ok": has_audio}

    all_text = "".join(sc["narration"] + sc["screen_text"] for sc in scenes)
    missing = [t for t in (_amount_str(i) for i in recipe["ingredients"]) if t not in all_text]
    report["checks"]["ingredients_verbatim"] = {"ok": not missing, "missing": missing}

    heats = [s["heat"] for s in recipe["steps"] if s.get("heat") and s["heat"] != "无"]
    missing_heat = [h for h in set(heats) if h not in all_text]
    report["checks"]["heat_mentioned"] = {"ok": not missing_heat, "missing": missing_heat}

    report["pass"] = all(c["ok"] for c in report["checks"].values())
    (workdir / "qc_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    r = run(sys.argv[1], sys.argv[2])
    print(json.dumps(r, ensure_ascii=False, indent=2))
    sys.exit(0 if r["pass"] else 1)
