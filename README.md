# 猫猫炒菜 🐱🍳

全自动动画美食视频系统：一只动画猫做美食的竖屏短视频（<60s），基于真实菜谱、观众可一比一还原。选题 → 制作 → 渲染 → 上传B站 → 数据分析，全流程无人值守。

- **架构设计**：[ARCHITECTURE.md](ARCHITECTURE.md)（v2，含多环境发布工程）
- **Agent 契约**：[CLAUDE.md](CLAUDE.md) — 用 Claude Code 迭代本系统前必读
- **下一步操作**：[NEXT_STEPS.md](NEXT_STEPS.md)

## 快速开始（开发环境）

```bash
git clone --recurse-submodules <repo-url>
cd maomao-cooking
cp .env.example .env        # 填入 dev 环境配置
bash scripts/setup.sh
pytest tests/
```

## 运行环境

| 机器 | 角色 |
|---|---|
| Mac mini | 编排/文案/渲染/上传/数据拉取 worker |
| 2070Ti PC | GPU worker（SDXL + 猫 LoRA 出图、超分） |
| Azure | 队列、状态表、Blob、TTS、状态面板 |
