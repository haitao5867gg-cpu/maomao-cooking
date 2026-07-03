"""Stage 3: narration.json → audio/NN_scene.wav（Azure Speech TTS）。

生产路径：直接调 Azure Speech REST（需 AZURE_SPEECH_KEY/REGION 或 Entra token）。
幂等：已存在且非空的 wav 跳过——因此音频也可由外部工具（如 Azure MCP）预先
写入 audio/ 目录，本 stage 只补缺 + 校验完整性。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx

VOICE = "zh-CN-XiaoxiaoNeural"
FORMAT = "riff-24khz-16bit-mono-pcm"


def synth_azure(text: str, out: Path) -> None:
    key, region = os.environ["AZURE_SPEECH_KEY"], os.environ["AZURE_SPEECH_REGION"]
    ssml = (
        f"<speak version='1.0' xml:lang='zh-CN'>"
        f"<voice name='{VOICE}'><prosody rate='+15%'>{text}</prosody></voice></speak>"
    )
    r = httpx.post(
        f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1",
        headers={
            "Ocp-Apim-Subscription-Key": key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": FORMAT,
        },
        content=ssml.encode("utf-8"),
        timeout=60,
    )
    r.raise_for_status()
    out.write_bytes(r.content)


def run(workdir: str | Path, force: bool = False) -> Path:
    workdir = Path(workdir)
    scenes = json.loads((workdir / "narration.json").read_text(encoding="utf-8"))
    outdir = workdir / "audio"
    outdir.mkdir(exist_ok=True)
    missing = []
    for i, sc in enumerate(scenes):
        out = outdir / f"{i:02d}_{sc['scene']}.wav"
        if out.exists() and out.stat().st_size > 1000 and not force:
            continue
        if os.environ.get("AZURE_SPEECH_KEY"):
            synth_azure(sc["narration"], out)
        else:
            missing.append(out.name)
    if missing:
        raise SystemExit(f"缺少音频且无 AZURE_SPEECH_KEY，待补：{missing}")
    return outdir


if __name__ == "__main__":
    print(run(sys.argv[1], force="--force" in sys.argv))
