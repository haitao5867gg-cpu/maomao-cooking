"""Stage 2: narration.json → 每场景 1080x1920 PNG。

P1 占位画风：程序绘制的卡通猫厨师 + 渐变背景 + 大字排版。
P2 起本 stage 的猫图改由 2070Ti SDXL+LoRA 生成，排版层不变。
幂等：已存在的场景图跳过。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
FONT = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc"
PALETTE = {
    "hook": ((255, 179, 71), (255, 236, 179)),
    "ingredients": ((255, 214, 98), (255, 244, 214)),
    "step": ((255, 194, 120), (255, 240, 200)),
    "outro": ((255, 160, 90), (255, 230, 190)),
}


def _font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT, size)


def _gradient(top: tuple, bottom: tuple) -> Image.Image:
    img = Image.new("RGB", (W, H))
    px = img.load()
    for y in range(H):
        t = y / H
        c = tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
        for x in range(W):
            px[x, y] = c
    return img


def draw_cat(d: ImageDraw.ImageDraw, cx: int, cy: int, r: int) -> None:
    """简笔猫厨师：橘猫脸 + 厨师帽。P2 换 SDXL 出图。"""
    orange, dark, white = (240, 150, 60), (60, 40, 30), (255, 255, 255)
    d.polygon([(cx - r, cy - r // 3), (cx - r + r // 3, cy - r - r // 2), (cx - r // 4, cy - r + r // 5)], fill=orange, outline=dark, width=6)
    d.polygon([(cx + r, cy - r // 3), (cx + r - r // 3, cy - r - r // 2), (cx + r // 4, cy - r + r // 5)], fill=orange, outline=dark, width=6)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=orange, outline=dark, width=8)
    hat_w, hat_h = int(r * 1.1), int(r * 0.75)
    d.rounded_rectangle([cx - hat_w // 2, cy - r - hat_h // 2, cx + hat_w // 2, cy - r + hat_h // 3], radius=30, fill=white, outline=dark, width=6)
    for i in (-1, 0, 1):
        d.ellipse([cx + i * hat_w // 3 - r // 4, cy - r - hat_h // 2 - r // 5, cx + i * hat_w // 3 + r // 4, cy - r - hat_h // 2 + r // 5], fill=white, outline=dark, width=6)
    for sx in (-1, 1):
        ex = cx + sx * r // 2.5
        d.ellipse([ex - r // 8, cy - r // 6, ex + r // 8, cy + r // 24], fill=dark)
    d.polygon([(cx - r // 12, cy + r // 6), (cx + r // 12, cy + r // 6), (cx, cy + r // 4)], fill=(230, 120, 120))
    d.arc([cx - r // 5, cy + r // 6, cx, cy + r // 2.5], 0, 180, fill=dark, width=5)
    d.arc([cx, cy + r // 6, cx + r // 5, cy + r // 2.5], 0, 180, fill=dark, width=5)
    for sx in (-1, 1):
        for dy in (-r // 10, 0, r // 10):
            x0 = cx + sx * r * 0.55
            d.line([x0, cy + r // 5 + dy, x0 + sx * r * 0.45, cy + r // 6 + dy * 2], fill=dark, width=4)


def _wrap(text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    lines, cur = [], ""
    for ch in text:
        if font.getlength(cur + ch) > max_w:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def render_scene(sc: dict, out: Path) -> None:
    kind = "step" if sc["scene"].startswith("step") else sc["scene"]
    img = _gradient(*PALETTE.get(kind, PALETTE["step"]))
    d = ImageDraw.Draw(img)
    draw_cat(d, W // 2, 420, 220)

    if kind == "step":
        d.text((W // 2, 780), f"第 {sc['scene'].split('_')[1]} 步", font=_font(72), fill=(120, 70, 20), anchor="mm")

    body_font = _font(58)
    y = 900
    for line in _wrap(sc["narration"], body_font, W - 160):
        d.text((W // 2, y), line, font=body_font, fill=(60, 40, 30), anchor="mm")
        y += 86

    bar_font = _font(48)
    bar_lines = _wrap(sc["screen_text"], bar_font, W - 200)
    bar_h = 60 + len(bar_lines) * 72
    d.rounded_rectangle([60, H - 260 - bar_h, W - 60, H - 200], radius=36, fill=(60, 40, 30))
    by = H - 260 - bar_h + 60
    for line in bar_lines:
        d.text((W // 2, by), line, font=bar_font, fill=(255, 220, 150), anchor="mm")
        by += 72

    img.save(out)


def run(workdir: str | Path, force: bool = False) -> Path:
    workdir = Path(workdir)
    scenes = json.loads((workdir / "narration.json").read_text(encoding="utf-8"))
    outdir = workdir / "scenes"
    outdir.mkdir(exist_ok=True)
    for i, sc in enumerate(scenes):
        out = outdir / f"{i:02d}_{sc['scene']}.png"
        if not out.exists() or force:
            render_scene(sc, out)
    return outdir


if __name__ == "__main__":
    print(run(sys.argv[1], force="--force" in sys.argv))
