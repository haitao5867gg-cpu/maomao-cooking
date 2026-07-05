"""往 GPU 队列发一个测试任务，验证 2070Ti worker 能领取并生图。
用法: python worker/test_send_job.py
"""
import json
import os
from azure.storage.queue import QueueClient

CONN = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "")
if not CONN:
    # 从 .env-maomao 读取
    env_file = os.path.expanduser("~/.env-maomao")
    if os.path.exists(env_file):
        for line in open(env_file):
            if "=" in line:
                k, v = line.strip().split("=", 1)
                os.environ[k] = v
        CONN = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "")

ENV = os.environ.get("MAOMAO_ENV", "dev")
QUEUE = f"{ENV}-gpu-jobs"

job = {
    "video_id": "test-001",
    "job_type": "scene_batch",
    "scenes": [
        {
            "scene_id": "00_test",
            "prompt": (
                "cute orange tabby cat chef, round chubby face, big amber eyes, "
                "white chef hat, red apron, happy expression, standing in cozy kitchen, "
                "holding a wooden spatula, front view, upper body, "
                "3D render, pixar style, soft studio lighting, vibrant colors"
            ),
            "negative_prompt": (
                "realistic photo, human, deformed, extra limbs, extra tails, "
                "text, watermark, blurry, dark, scary, ugly"
            ),
            "seed": 42,
            "width": 832,
            "height": 1216,
            "steps": 28,
            "cfg_scale": 6.5,
        }
    ],
    "output_blob_prefix": "gpu-output/test-001/",
}

client = QueueClient.from_connection_string(CONN, QUEUE)
msg = client.send_message(json.dumps(job))
print(f"[OK] 测试任务已发送到 {QUEUE}")
print(f"     video_id: test-001")
print(f"     场景数: 1 (猫厨师 Pixar 风格)")
print(f"     2070Ti 应该在 30s 内领取并开始生图")
