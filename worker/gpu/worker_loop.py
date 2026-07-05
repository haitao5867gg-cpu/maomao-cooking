"""GPU Worker 主循环：轮询 Azure Queue → 调推理 → 上传 Blob → 回写状态。

在 2070Ti 上作为 systemd 服务运行：
    python -m worker.gpu.worker_loop

首次启动加载模型到 VRAM（约 30-60s），之后常驻。
无消息时每 30s 空转一次，几乎零 CPU/GPU 开销。
"""
from __future__ import annotations

import json
import os
import signal
import sys
import time
import traceback
from pathlib import Path

POLL_INTERVAL = int(os.environ.get("MAOMAO_GPU_POLL_INTERVAL", "30"))
MAX_RETRIES = 2
ENV = os.environ.get("MAOMAO_ENV", "dev")
QUEUE_NAME = f"{ENV}-gpu-jobs"
POISON_QUEUE = f"{ENV}-gpu-jobs-poison"
BLOB_CONTAINER = f"{ENV}-gpu-output"
TABLE_NAME = f"{ENV}tasks"
LOCAL_WORKDIR = Path(os.environ.get("MAOMAO_GPU_WORKDIR", "/tmp/maomao-gpu"))

_shutdown = False


def _handle_signal(signum, frame):
    global _shutdown
    print(f"\n[worker] 收到信号 {signum}，完成当前任务后退出...")
    _shutdown = True


def _get_queue_client():
    from azure.storage.queue import QueueClient
    conn = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
    client = QueueClient.from_connection_string(conn, QUEUE_NAME)
    try:
        client.create_queue()
    except Exception:
        pass  # 已存在
    return client


def _get_poison_queue_client():
    from azure.storage.queue import QueueClient
    conn = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
    client = QueueClient.from_connection_string(conn, POISON_QUEUE)
    try:
        client.create_queue()
    except Exception:
        pass  # 已存在
    return client


def _get_blob_container():
    from azure.storage.blob import ContainerClient
    conn = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
    client = ContainerClient.from_connection_string(conn, BLOB_CONTAINER)
    try:
        client.create_container()
    except Exception:
        pass  # 已存在
    return client


def _get_table_client():
    from azure.data.tables import TableClient
    conn = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
    client = TableClient.from_connection_string(conn, TABLE_NAME)
    try:
        client.create_table()
    except Exception:
        pass
    return client


def _upload_results(blob_client, output_dir: Path, blob_prefix: str) -> list[str]:
    """上传目录下所有 PNG 到 Blob，返回 blob 名列表。"""
    uploaded = []
    for f in sorted(output_dir.glob("*.png")):
        blob_name = f"{blob_prefix}{f.name}"
        with open(f, "rb") as data:
            blob_client.upload_blob(name=blob_name, data=data, overwrite=True)
        uploaded.append(blob_name)
        print(f"[worker] 已上传: {blob_name}")
    return uploaded


def _update_task_table(table_client, video_id: str, status: str, blob_paths: list[str] | None = None):
    """回写任务表状态。"""
    entity = {
        "PartitionKey": video_id,
        "RowKey": "gpu",
        "status": status,
    }
    if blob_paths:
        entity["blob_paths"] = json.dumps(blob_paths)
    table_client.upsert_entity(entity)
    print(f"[worker] 任务表已更新: {video_id} → {status}")


def process_job(pipe, job: dict, blob_client, table_client) -> None:
    """处理单个 GPU 作业。"""
    from worker.gpu.inference import generate_batch

    video_id = job["video_id"]
    scenes = job["scenes"]
    blob_prefix = job.get("output_blob_prefix", f"gpu-output/{video_id}/")

    output_dir = LOCAL_WORKDIR / video_id
    print(f"[worker] 开始作业: {video_id} ({len(scenes)} 场景)")

    _update_task_table(table_client, video_id, "in_progress")

    paths = generate_batch(pipe, scenes, output_dir)
    uploaded = _upload_results(blob_client, output_dir, blob_prefix)

    _update_task_table(table_client, video_id, "done", uploaded)
    print(f"[worker] 作业完成: {video_id}")


def main() -> None:
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    print(f"[worker] 猫猫炒菜 GPU Worker 启动")
    print(f"[worker] 环境={ENV}  队列={QUEUE_NAME}  轮询间隔={POLL_INTERVAL}s")

    # 1. 加载模型（一次性）
    from worker.gpu.inference import load_pipeline
    pipe = load_pipeline()

    # 2. 初始化 Azure 客户端
    queue_client = _get_queue_client()
    poison_client = _get_poison_queue_client()
    blob_client = _get_blob_container()
    table_client = _get_table_client()

    LOCAL_WORKDIR.mkdir(parents=True, exist_ok=True)

    # 3. 主循环
    print(f"[worker] 开始轮询 {QUEUE_NAME}...")
    while not _shutdown:
        messages = queue_client.receive_messages(max_messages=1, visibility_timeout=600)
        msg = next(iter(messages), None)

        if msg is None:
            time.sleep(POLL_INTERVAL)
            continue

        try:
            job = json.loads(msg.content)
        except json.JSONDecodeError as e:
            # 消息体不是合法 JSON（例如被 Base64 编码过）——重试无意义，直接进死信
            print(f"[worker] 消息不是合法 JSON，移入死信队列: {e}")
            poison_client.send_message(msg.content)
            queue_client.delete_message(msg)
            continue

        try:
            process_job(pipe, job, blob_client, table_client)
            queue_client.delete_message(msg)
        except Exception as e:
            print(f"[worker] 作业失败: {e}")
            traceback.print_exc()

            if msg.dequeue_count >= MAX_RETRIES:
                print(f"[worker] 重试次数已达上限，移入死信队列")
                poison_client.send_message(msg.content)
                queue_client.delete_message(msg)
                # TODO: 发送告警（Telegram/Bark）
            else:
                print(f"[worker] 将重试 (第 {msg.dequeue_count}/{MAX_RETRIES} 次)")

    print("[worker] GPU Worker 已安全退出")


if __name__ == "__main__":
    main()
