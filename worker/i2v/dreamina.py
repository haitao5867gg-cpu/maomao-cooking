"""即梦 CLI（dreamina）封装：提交 → 轮询 → 下载。

前提：机器上已安装并登录即梦 CLI（安装 `curl -fsSL https://jimeng.jianying.com/cli | bash`，
登录 `dreamina login`，自检 `dreamina user_credit`）。登录态在 ~/.dreamina_cli/，不进 git。

注意：每次生成消耗即梦积分（与网页 Agent 模式同价），调用方需自带预算护栏。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

BIN = os.environ.get("MAOMAO_DREAMINA_BIN", "dreamina")
SESSION = os.environ.get("MAOMAO_DREAMINA_SESSION", "")  # 可选：即梦会话隔离

OK_STATUSES = {"success", "succeed", "done"}
PENDING_STATUSES = {"querying", "queueing", "processing", "running", "pending"}


class DreaminaError(RuntimeError):
    pass


def _run(args: list[str], timeout: int = 900) -> str:
    cmd = [BIN, *args]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as e:
        raise DreaminaError(
            f"找不到 {BIN}。请先安装并登录即梦 CLI（见本文件 docstring）"
        ) from e
    if p.returncode != 0:
        raise DreaminaError(f"{' '.join(cmd[:2])} 失败: {(p.stderr or p.stdout).strip()[:500]}")
    return p.stdout


def _parse_json(text: str) -> dict:
    """CLI 输出可能带日志前后缀，取第一个 '{' 到最后一个 '}' 之间解析。"""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    a, b = text.find("{"), text.rfind("}")
    if a == -1 or b <= a:
        raise DreaminaError(f"无法从 CLI 输出解析 JSON: {text.strip()[:300]}")
    return json.loads(text[a : b + 1])


def image2video(image: str | Path, prompt: str, duration: int = 5,
                video_resolution: str = "720p", poll: int = 60) -> dict:
    """提交图生视频任务，返回含 submit_id / gen_status 的 dict。"""
    args = [
        "image2video", "--image", str(image), f"--prompt={prompt}",
        f"--duration={duration}", f"--video_resolution={video_resolution}",
        f"--poll={poll}",
    ]
    if SESSION:
        args.append(f"--session={SESSION}")
    res = _parse_json(_run(args))
    if "submit_id" not in res:
        raise DreaminaError(f"提交结果缺少 submit_id: {res}")
    return res


def wait(submit_id: str, timeout_sec: int = 1200, interval_sec: int = 30) -> dict:
    """轮询任务直到成功；失败或超时抛 DreaminaError。"""
    deadline = time.monotonic() + timeout_sec
    while True:
        res = _parse_json(_run(["query_result", f"--submit_id={submit_id}"]))
        status = str(res.get("gen_status", "")).lower()
        if status in OK_STATUSES:
            return res
        if status not in PENDING_STATUSES:
            raise DreaminaError(f"任务 {submit_id} 状态异常: {status or res}")
        if time.monotonic() > deadline:
            raise DreaminaError(f"任务 {submit_id} 超时（>{timeout_sec}s），可稍后手动 query_result")
        time.sleep(interval_sec)


def download(submit_id: str, dest: str | Path, suffix: str = ".mp4") -> Path:
    """下载任务产物到临时目录，返回其中最新的目标文件。"""
    dest = Path(dest)
    tmp = dest / f".dl_{submit_id}"
    tmp.mkdir(parents=True, exist_ok=True)
    _run(["query_result", f"--submit_id={submit_id}", f"--download_dir={tmp}"])
    files = sorted(tmp.rglob(f"*{suffix}"), key=lambda p: p.stat().st_mtime)
    if not files:
        shutil.rmtree(tmp, ignore_errors=True)
        raise DreaminaError(f"任务 {submit_id} 下载目录中没有 {suffix} 文件")
    return files[-1]


def generate_clip(image: str | Path, prompt: str, out: str | Path,
                  duration: int = 5, video_resolution: str = "720p") -> Path:
    """一站式：提交 + 等待 + 下载 + 归位到 out。幂等由调用方负责。"""
    out = Path(out)
    res = image2video(image, prompt, duration=duration, video_resolution=video_resolution)
    submit_id = str(res["submit_id"])
    if str(res.get("gen_status", "")).lower() not in OK_STATUSES:
        wait(submit_id)
    produced = download(submit_id, out.parent)
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(produced), out)
    shutil.rmtree(produced.parent, ignore_errors=True)
    return out
