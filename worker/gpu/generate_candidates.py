"""P2: 猫主角形象候选图批量生成。

在 2070Ti 机器上运行（需 WebUI 已启动）：
    pip install requests
    python worker/gpu/generate_candidates.py

3 套画风 × 12 个固定 seed = 36 张候选，输出到 assets/candidates/batch01/，
每张附 sidecar json（prompt/seed 可复现）。跑完 git push 回仓库供筛选。
选定画风后，该风格词 + seed 即成为角色一致性基线，并用于 LoRA 训练集生成。
"""
from __future__ import annotations

import base64
import json
import time
from pathlib import Path

import requests

API = "http://127.0.0.1:7860/sdapi/v1/txt2img"
OUT = Path(__file__).resolve().parents[2] / "assets" / "candidates" / "batch01"

# 角色核心设定（所有画风共用，未来写进 CLAUDE.md 角色规范）
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


def gen(style_key: str, style_words: str, seed: int) -> None:
    out_img = OUT / f"{style_key}_seed{seed}.jpg"
    if out_img.exists():
        return
    payload = {
        "prompt": f"{CHARACTER}, {style_words}",
        "negative_prompt": NEGATIVE,
        "seed": seed,
        "steps": 28,
        "cfg_scale": 6.5,
        "width": 832,
        "height": 1216,
        "sampler_name": "DPM++ 2M Karras",
    }
    t0 = time.time()
    r = requests.post(API, json=payload, timeout=600)
    r.raise_for_status()
    img_b64 = r.json()["images"][0]
    # 存 jpg 控制仓库体积
    from io import BytesIO

    from PIL import Image

    Image.open(BytesIO(base64.b64decode(img_b64))).convert("RGB").save(out_img, quality=92)
    out_img.with_suffix(".json").write_text(
        json.dumps({k: payload[k] for k in ("prompt", "negative_prompt", "seed", "steps", "cfg_scale", "width", "height", "sampler_name")}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"✓ {out_img.name}  ({time.time() - t0:.0f}s)")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    total = len(STYLES) * len(SEEDS)
    print(f"开始生成 {total} 张候选图 → {OUT}")
    for style_key, style_words in STYLES.items():
        for seed in SEEDS:
            gen(style_key, style_words, seed)
    print("完成。接下来：")
    print("  git checkout -b p2-cat-candidates && git add assets/candidates && git commit -m 'P2: 猫主角候选图 batch01' && git push -u origin p2-cat-candidates")


if __name__ == "__main__":
    main()
