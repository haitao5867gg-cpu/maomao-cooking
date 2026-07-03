"""P2: 猫主角形象候选图批量生成。

在 2070Ti 机器上运行：
    pip install -r worker/gpu/setup/requirements-gpu.txt
    python -m worker.gpu.generate_candidates

3 套画风 × 12 个固定 seed = 36 张候选，输出到 assets/candidates/batch01/，
每张附 sidecar json（prompt/seed 可复现）。
选定画风后，该风格词 + seed 即成为角色一致性基线，并用于 LoRA 训练集生成。

结果通过 Azure Blob 上传供 Mac 端筛选（不再依赖 git 传送带或 HTTP 文件服务器）。
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from worker.gpu.inference import load_pipeline, generate_image

# 输出到仓库内 assets/candidates/batch01/
OUT = Path(__file__).resolve().parents[2] / "assets" / "candidates" / "batch01"

# 角色核心设定（所有画风共用）
CHARACTER = (
    "cute orange tabby cat chef, round chubby face, big amber eyes, "
    "white chef hat, red apron, happy expression, standing in cozy kitchen, "
    "holding a wooden spatula, front view, upper body"
)
NEGATIVE = (
    "realistic photo, human, deformed, extra limbs, extra tails, text, "
    "watermark, blurry, dark, scary, ugly"
)

STYLES = {
    "A_3d_pixar": "3D render, pixar style, soft studio lighting, vibrant colors, smooth shading, octane render",
    "B_flat_kawaii": "flat 2D kawaii illustration, thick clean outlines, pastel colors, simple shapes, sticker style, white background accents",
    "C_ghibli_soft": "ghibli style anime, soft watercolor shading, warm afternoon light, storybook illustration, gentle color palette",
}
SEEDS = [42, 101, 202, 303, 404, 505, 606, 707, 808, 909, 1234, 5678]


def gen(pipe, style_key: str, style_words: str, seed: int) -> None:
    out_img = OUT / f"{style_key}_seed{seed}.png"
    if out_img.exists():
        return

    params = {
        "prompt": f"{CHARACTER}, {style_words}",
        "negative_prompt": NEGATIVE,
        "seed": seed,
        "width": 832,
        "height": 1216,
        "steps": 28,
        "cfg_scale": 6.5,
    }
    t0 = time.time()
    img = generate_image(pipe, **params)
    img.save(out_img)

    out_img.with_suffix(".json").write_text(
        json.dumps(params, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[OK] {out_img.name}  ({time.time() - t0:.0f}s)")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    total = len(STYLES) * len(SEEDS)
    print(f"加载模型...")
    pipe = load_pipeline()
    print(f"开始生成 {total} 张候选图 → {OUT}")
    for style_key, style_words in STYLES.items():
        for seed in SEEDS:
            gen(pipe, style_key, style_words, seed)
    print(f"\n完成！{total} 张候选图已保存到 {OUT}")


if __name__ == "__main__":
    main()
