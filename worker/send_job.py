#!/usr/bin/env python3
"""通用队列任务发送工具。

用法:
    # 发送 JSON 文件
    .venv/bin/python3 worker/send_job.py job.json

    # 发送内联 JSON
    .venv/bin/python3 worker/send_job.py '{"video_id":"test","job_type":"scene_batch",...}'

    # 从 stdin 读取
    cat job.json | .venv/bin/python3 worker/send_job.py -

自动从 ~/.env-maomao 读取连接串和环境配置。
"""
import json
import os
import sys
from pathlib import Path


def _load_env():
    """从 ~/.env-maomao 加载环境变量。"""
    env_file = Path.home() / ".env-maomao"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k, v)


def send_job(job: dict) -> None:
    """发送一个任务到 GPU 队列。"""
    from azure.storage.queue import QueueClient

    conn = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "")
    if not conn:
        print("[ERROR] AZURE_STORAGE_CONNECTION_STRING 为空，请检查 ~/.env-maomao")
        sys.exit(1)

    env = os.environ.get("MAOMAO_ENV", "dev")
    queue_name = f"{env}-gpu-jobs"

    client = QueueClient.from_connection_string(conn, queue_name)
    client.send_message(json.dumps(job, ensure_ascii=False))

    scenes = job.get("scenes", [])
    print(f"[OK] 已发送到 {queue_name}")
    print(f"     video_id: {job.get('video_id', '?')}")
    print(f"     场景数: {len(scenes)}")
    if scenes:
        print(f"     steps: {scenes[0].get('steps', '?')}, cfg_scale: {scenes[0].get('cfg_scale', '?')}")


def main():
    _load_env()

    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    arg = sys.argv[1]

    if arg == "-":
        data = sys.stdin.read()
    elif arg.endswith(".json") and Path(arg).exists():
        data = Path(arg).read_text()
    else:
        data = arg

    try:
        job = json.loads(data)
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON 解析失败: {e}")
        sys.exit(1)

    # 支持批量发送（JSON 数组）
    if isinstance(job, list):
        for i, j in enumerate(job):
            print(f"\n--- 任务 {i+1}/{len(job)} ---")
            send_job(j)
    else:
        send_job(job)


if __name__ == "__main__":
    main()
