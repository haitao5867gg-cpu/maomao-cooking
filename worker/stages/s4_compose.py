"""Stage 4: scenes/*.png + audio/*.wav → final.mp4（ffmpeg 合成）。

每个场景时长 = 对应 wav 时长 + 0.4s 呼吸间隔；无音频时用 narration.json 估时。
输出 1080x1920 H.264 + AAC。幂等：final.mp4 已存在则跳过。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

PAD = 0.4
PRESET = os.environ.get("MAOMAO_FFMPEG_PRESET", "fast")


def _dur(wav: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(wav)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def run(workdir: str | Path, force: bool = False) -> Path:
    workdir = Path(workdir)
    final = workdir / "final.mp4"
    if final.exists() and not force:
        return final

    scenes = json.loads((workdir / "narration.json").read_text(encoding="utf-8"))
    segdir = workdir / "segments"
    segdir.mkdir(exist_ok=True)
    concat_lines = []

    for i, sc in enumerate(scenes):
        stem = f"{i:02d}_{sc['scene']}"
        png = workdir / "scenes" / f"{stem}.png"
        wav = workdir / "audio" / f"{stem}.wav"
        seg = segdir / f"{stem}.mp4"
        dur = (_dur(wav) if wav.exists() else sc["est_duration_sec"]) + PAD
        cmd = ["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", str(png)]
        if wav.exists():
            cmd += ["-i", str(wav)]
        else:
            cmd += ["-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono"]
        cmd += [
            "-t", f"{dur:.2f}", "-r", "30",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", PRESET,
            "-c:a", "aac", "-b:a", "128k",
            str(seg),
        ]
        subprocess.run(cmd, check=True)
        concat_lines.append(f"file '{seg.name}'")

    (segdir / "concat.txt").write_text("\n".join(concat_lines), encoding="utf-8")
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
         "-i", str(segdir / "concat.txt"), "-c", "copy", str(final)],
        check=True,
    )
    return final


if __name__ == "__main__":
    print(run(sys.argv[1], force="--force" in sys.argv))
