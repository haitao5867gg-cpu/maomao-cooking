"""s2b_i2v + dreamina 封装单测（全 mock，不触网不耗积分）。"""
import json
from pathlib import Path

import pytest

from worker.i2v import dreamina
from worker.stages import s2b_i2v


def _mk_workdir(tmp_path: Path, n: int = 2) -> Path:
    wd = tmp_path / "proj"
    (wd / "scenes").mkdir(parents=True)
    scenes = [{"scene": "hook", "text": "x", "est_duration_sec": 3},
              {"scene": "step1", "text": "y", "est_duration_sec": 5}][:n]
    (wd / "narration.json").write_text(json.dumps(scenes), encoding="utf-8")
    for i, sc in enumerate(scenes):
        (wd / "scenes" / f"{i:02d}_{sc['scene']}.png").write_bytes(b"png")
    return wd


def test_parse_json_with_log_noise():
    out = 'INFO downloading...\n{"submit_id": "abc", "gen_status": "querying"}\ndone'
    assert dreamina._parse_json(out)["submit_id"] == "abc"


def test_parse_json_failure():
    with pytest.raises(dreamina.DreaminaError):
        dreamina._parse_json("no json here")


def test_motion_for_maps_step_variants():
    assert s2b_i2v.motion_for("step3") == s2b_i2v.MOTION["step"]
    assert s2b_i2v.motion_for("hook")[1] == 3


def test_stage_generates_and_is_idempotent(tmp_path, monkeypatch):
    wd = _mk_workdir(tmp_path)
    calls = []

    def fake_generate(image, prompt, out, duration=5, video_resolution="720p"):
        calls.append((Path(image).name, prompt, duration))
        Path(out).write_bytes(b"mp4")
        return Path(out)

    monkeypatch.setattr(dreamina, "generate_clip", fake_generate)
    outdir = s2b_i2v.run(wd)
    assert sorted(p.name for p in outdir.glob("*.mp4")) == ["00_hook.mp4", "01_step1.mp4"]
    assert len(calls) == 2
    assert calls[0][2] == 3  # hook 3s
    # 幂等：重跑不再调用
    s2b_i2v.run(wd)
    assert len(calls) == 2


def test_stage_budget_guard(tmp_path, monkeypatch):
    wd = _mk_workdir(tmp_path)
    monkeypatch.setenv("MAOMAO_I2V_MAX_CLIPS_PER_RUN", "1")
    monkeypatch.setattr(dreamina, "generate_clip",
                        lambda image, prompt, out, **kw: Path(out).write_bytes(b"mp4") or Path(out))
    with pytest.raises(dreamina.DreaminaError, match="预算"):
        s2b_i2v.run(wd)
    # 已生成 1 个，续跑补齐剩下 1 个
    monkeypatch.setenv("MAOMAO_I2V_MAX_CLIPS_PER_RUN", "12")
    s2b_i2v.run(wd)
    assert len(list((wd / "clips").glob("*.mp4"))) == 2


def test_stage_missing_first_frame(tmp_path, monkeypatch):
    wd = _mk_workdir(tmp_path)
    (wd / "scenes" / "00_hook.png").unlink()
    monkeypatch.setattr(dreamina, "generate_clip", lambda *a, **k: None)
    with pytest.raises(FileNotFoundError):
        s2b_i2v.run(wd)


def test_generate_clip_flow(tmp_path, monkeypatch):
    """submit(querying) → wait(success) → download 归位。"""
    submitted = {}

    def fake_run(args, timeout=900):
        if args[0] == "image2video":
            submitted["prompt"] = args[3]
            return '{"submit_id": "s1", "gen_status": "querying"}'
        if args[0] == "query_result":
            dl = [a for a in args if a.startswith("--download_dir=")]
            if dl:
                d = Path(dl[0].split("=", 1)[1])
                d.mkdir(parents=True, exist_ok=True)
                (d / "video.mp4").write_bytes(b"mp4")
            return '{"submit_id": "s1", "gen_status": "success"}'
        raise AssertionError(args)

    monkeypatch.setattr(dreamina, "_run", fake_run)
    monkeypatch.setattr(dreamina.time, "sleep", lambda s: None)
    out = tmp_path / "clips" / "00_hook.mp4"
    got = dreamina.generate_clip(tmp_path / "f.png", "镜头推近", out, duration=3)
    assert got == out and out.read_bytes() == b"mp4"
    assert submitted["prompt"] == "--prompt=镜头推近"


def test_wait_failure_status(monkeypatch):
    monkeypatch.setattr(dreamina, "_run", lambda a, timeout=900: '{"gen_status": "failed"}')
    with pytest.raises(dreamina.DreaminaError, match="状态异常"):
        dreamina.wait("s1")
