"""管线运行器：python -m worker.pipeline <recipe.json> <video-id>

按序执行 s1→s5，每个 stage 幂等，失败即停。
P3 起由队列 worker 按 stage 粒度调度，本运行器保留用于本地/CI 全链路测试。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from worker.stages import s1_narration, s2_scenes, s2b_i2v, s3_tts, s4_compose, s5_qc


def run(recipe_path: str, video_id: str, base: str = "projects") -> dict:
    workdir = Path(base) / video_id
    print(f"[s1] narration → {s1_narration.run(recipe_path, workdir)}")
    print(f"[s2] scenes    → {s2_scenes.run(workdir)}")
    if os.environ.get("MAOMAO_I2V") == "1":  # 需机器已安装并登录即梦 CLI
        print(f"[s2b] i2v      → {s2b_i2v.run(workdir)}")
    print(f"[s3] tts       → {s3_tts.run(workdir)}")
    print(f"[s4] compose   → {s4_compose.run(workdir)}")
    report = s5_qc.run(recipe_path, workdir)
    print(f"[s5] qc        → pass={report['pass']}")
    return report


if __name__ == "__main__":
    report = run(sys.argv[1], sys.argv[2])
    sys.exit(0 if report["pass"] else 1)
