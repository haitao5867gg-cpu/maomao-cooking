"""diffusers 推理封装：模型加载、LoRA 注入、单张/批量生图。

设计目标：
- 模型加载一次，常驻 VRAM，跨任务复用
- 8GB 显存安全（float16 + VAE tiling + attention slicing）
- 确定性输出（固定 seed → 固定结果）
"""
from __future__ import annotations

import os
from pathlib import Path

import torch
from PIL import Image

# 模型配置（可通过环境变量覆盖）
DEFAULT_MODEL = os.environ.get("MAOMAO_SD_MODEL", "stabilityai/stable-diffusion-xl-base-1.0")
# fp16-fix VAE：解码不需要升 float32，避免 8GB 显存溢出到共享内存导致 3-4 倍降速
DEFAULT_VAE = os.environ.get("MAOMAO_SD_VAE", "madebyollin/sdxl-vae-fp16-fix")
LORA_PATH = os.environ.get("MAOMAO_LORA_PATH", "")  # P2 训练后填入
LORA_WEIGHT = float(os.environ.get("MAOMAO_LORA_WEIGHT", "0.8"))
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


def load_pipeline(model_id: str | None = None, lora_path: str | None = None):
    """加载 SDXL pipeline，优化 8GB 显存。返回 pipeline 对象。"""
    from diffusers import AutoencoderKL, StableDiffusionXLPipeline

    model_id = model_id or DEFAULT_MODEL
    print(f"[inference] 加载模型: {model_id} → {DEVICE}")

    # fp16-fix VAE（约 320MB，首次从 HF_ENDPOINT 下载）。
    # 官方 SDXL VAE 的 force_upcast=True 会在解码时升 float32，8GB 卡显存被顶爆后
    # 溢出到共享内存，之后所有推理降速 3-4 倍。fp16-fix 版无需 upcast。
    # 下载失败不致命：退回官方 VAE 继续跑（慢但可用）。
    vae = None
    try:
        vae = AutoencoderKL.from_pretrained(DEFAULT_VAE, torch_dtype=torch.float16)
        print(f"[inference] VAE: {DEFAULT_VAE} (fp16, no upcast)")
    except Exception as e:
        print(f"[inference] 警告: fp16-fix VAE 加载失败（{e}），退回官方 VAE（速度会慢）")

    kwargs = dict(
        torch_dtype=torch.float16,
        variant="fp16",
        use_safetensors=True,
    )
    if vae is not None:
        kwargs["vae"] = vae
    pipe = StableDiffusionXLPipeline.from_pretrained(model_id, **kwargs)
    pipe = pipe.to(DEVICE)

    # 8GB 显存优化
    if hasattr(pipe.vae, "enable_tiling"):
        pipe.vae.enable_tiling()
    elif hasattr(pipe, "enable_vae_tiling"):
        pipe.enable_vae_tiling()
    if hasattr(pipe, "enable_attention_slicing"):
        pipe.enable_attention_slicing()

    # LoRA 注入（如果有）
    lora = lora_path or LORA_PATH
    if lora and Path(lora).exists():
        print(f"[inference] 加载 LoRA: {lora} (weight={LORA_WEIGHT})")
        pipe.load_lora_weights(lora)
        pipe.fuse_lora(lora_scale=LORA_WEIGHT)

    print("[inference] 模型加载完成，常驻 VRAM")
    return pipe


def generate_image(
    pipe,
    prompt: str,
    negative_prompt: str = "",
    seed: int = 42,
    width: int = 832,
    height: int = 1216,
    steps: int = 28,
    cfg_scale: float = 6.5,
) -> Image.Image:
    """单张生图。固定 seed 保证确定性。"""
    generator = torch.Generator(device=DEVICE).manual_seed(seed)

    result = pipe(
        prompt=prompt,
        negative_prompt=negative_prompt,
        generator=generator,
        width=width,
        height=height,
        num_inference_steps=steps,
        guidance_scale=cfg_scale,
    )

    return result.images[0]


def generate_batch(
    pipe,
    scenes: list[dict],
    output_dir: Path,
) -> list[Path]:
    """批量生图，逐张生成（8GB 显存不做 batch inference）。返回输出路径列表。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []

    for sc in scenes:
        out_path = output_dir / f"{sc['scene_id']}.png"
        if out_path.exists():
            print(f"[inference] 跳过已存在: {out_path.name}")
            paths.append(out_path)
            continue

        img = generate_image(
            pipe,
            prompt=sc["prompt"],
            negative_prompt=sc.get("negative_prompt", ""),
            seed=sc.get("seed", 42),
            width=sc.get("width", 832),
            height=sc.get("height", 1216),
            steps=sc.get("steps", 28),
            cfg_scale=sc.get("cfg_scale", 6.5),
        )
        img.save(out_path)
        print(f"[inference] 生成: {out_path.name}")
        paths.append(out_path)
        # 每张之间清缓存，避免碎片累积
        if DEVICE == "cuda":
            torch.cuda.empty_cache()

    return paths


if __name__ == "__main__":
    # 快速测试：下载模型并生成一张测试图
    import sys
    if "--download-model" in sys.argv:
        print("下载模型（首次需要几分钟）...")
        pipe = load_pipeline()
        print("模型下载完成！可以开始使用了。")
    else:
        pipe = load_pipeline()
        img = generate_image(pipe, prompt="cute orange tabby cat chef, test", seed=42, steps=10, width=512, height=512)
        img.save("test_output.png")
        print("测试图已保存: test_output.png")
