"""Stage 2b: scenes/NN_*.png（首帧）→ clips/NN_*.mp4（即梦 CLI 图生视频）。

- 运动 prompt 只描述动作/镜头，不重复角色外观（重复会诱导 i2v 重画角色导致不一致）。
- 模板按场景类型固定映射（铁律 #4：确定性，不接 LLM）。
- 幂等：clips/ 已存在的跳过。失败/未启用时 s4 自动回退静态图 loop，不阻塞管线。
- 预算护栏：单次运行最多生成 MAOMAO_I2V_MAX_CLIPS_PER_RUN 个（默认 12），防积分失控。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from worker.i2v import dreamina

# 场景类型 → (运动 prompt, 时长秒)。只写运镜与画面动态。
MOTION = {
    "hook":        ("镜头快速推近，锅中食物翻滚冒泡，热气与油光涌动", 3),
    "ingredients": ("俯拍视角，镜头缓慢横移扫过整齐排列的食材，光线柔和", 5),
    "step":        ("锅中食材翻炒滚动，蒸汽升腾，镜头轻微呼吸感晃动", 5),
    "outro":       ("镜头缓缓拉远，成品菜冒着热气，汤汁光泽流动", 5),
}


def motion_for(scene: str) -> tuple[str, int]:
    kind = "step" if scene.startswith("step") else scene
    return MOTION.get(kind, MOTION["step"])


def run(workdir: str | Path, force: bool = False) -> Path:
    workdir = Path(workdir)
    scenes = json.loads((workdir / "narration.json").read_text(encoding="utf-8"))
    outdir = workdir / "clips"
    outdir.mkdir(exist_ok=True)
    budget = int(os.environ.get("MAOMAO_I2V_MAX_CLIPS_PER_RUN", "12"))
    made = 0
    for i, sc in enumerate(scenes):
        stem = f"{i:02d}_{sc['scene']}"
        clip = outdir / f"{stem}.mp4"
        if clip.exists() and not force:
            continue
        png = workdir / "scenes" / f"{stem}.png"
        if not png.exists():
            raise FileNotFoundError(f"缺少首帧 {png}，先跑 s2_scenes")
        if made >= budget:
            raise dreamina.DreaminaError(
                f"已达单次运行预算 {budget} 个 clip（MAOMAO_I2V_MAX_CLIPS_PER_RUN），"
                f"确认积分后重跑即可续传（幂等）"
            )
        prompt, dur = motion_for(sc["scene"])
        dreamina.generate_clip(png, prompt, clip, duration=dur)
        made += 1
    return outdir


if __name__ == "__main__":
    print(run(sys.argv[1], force="--force" in sys.argv))
