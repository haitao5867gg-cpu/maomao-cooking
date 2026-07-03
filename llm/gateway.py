"""统一 LLM 网关 — 换供应商只改 .env，代码零改动。

支持任何 OpenAI 兼容接口：
  deepseek         https://api.deepseek.com          (生产默认，夜间避峰)
  azure_foundry    https://<res>.openai.azure.com    (备用)
  其他             任意 base_url

生产铁律：文案生成的输入必须是 recipe.json 的内容，prompt 模板在 llm/prompts/。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import httpx

PROMPTS_DIR = Path(__file__).parent / "prompts"


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    api_key: str
    model: str

    @classmethod
    def from_env(cls) -> "LLMConfig":
        return cls(
            base_url=os.environ["LLM_BASE_URL"].rstrip("/"),
            api_key=os.environ["LLM_API_KEY"],
            model=os.environ["LLM_MODEL"],
        )


def chat(messages: list[dict], config: LLMConfig | None = None, *, temperature: float = 0.7, timeout: float = 120) -> str:
    cfg = config or LLMConfig.from_env()
    resp = httpx.post(
        f"{cfg.base_url}/chat/completions",
        headers={"Authorization": f"Bearer {cfg.api_key}"},
        json={"model": cfg.model, "messages": messages, "temperature": temperature},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def render_prompt(template_name: str, **kwargs) -> str:
    """加载 llm/prompts/<name>.md 模板并填充变量。"""
    template = (PROMPTS_DIR / f"{template_name}.md").read_text(encoding="utf-8")
    return template.format(**kwargs)


def generate_narration(recipe: dict, config: LLMConfig | None = None) -> str:
    """从 recipe.json 生成旁白脚本。唯一合法的文案入口。"""
    prompt = render_prompt("narration", recipe_json=json.dumps(recipe, ensure_ascii=False, indent=2))
    return chat(
        [
            {"role": "system", "content": "你是美食短视频文案师。只能使用给定 JSON 中的数字和事实，禁止编造任何用量、火候、时长。"},
            {"role": "user", "content": prompt},
        ],
        config,
        temperature=0.7,
    )
