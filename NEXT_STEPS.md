# NEXT_STEPS — P1 收尾：出第一条视频

脚手架已完成（schema/校验器/LLM网关/CI/子模块均就绪，pytest 8/8 通过）。
以下步骤需要在**你的机器**上执行（涉及 GitHub 授权、API key、GPU）。

## 1. 推到 GitHub（5 分钟）

```bash
cd ~/Documents/Claude/Projects/猫猫炒菜
gh repo create maomao-cooking --private --source . --push
# 或手动：在 GitHub 建私有仓库后
# git remote add origin git@github.com:<you>/maomao-cooking.git && git push -u origin main
```

然后在 GitHub 仓库 Settings → Branches：保护 main，要求 PR + CI 通过。

## 2. Mac mini 环境（15 分钟）

```bash
brew install ffmpeg node gh
bash scripts/setup.sh          # 拉取 OpenMontage 子模块 + 装依赖
cp .env.example .env           # MAOMAO_ENV=dev
```

## 3. 出第一条视频（用 Claude Code agent 探索）

Mac mini 上装 Claude Code（走你的订阅，无需 API key）：

```bash
npm install -g @anthropic-ai/claude-code
cd ~/maomao-cooking && claude
```

对它说：

> 读 CLAUDE.md 和 openmontage/AGENT_GUIDE.md。用 recipe/samples/fanqie-chaodan.json 作为唯一事实来源，
> 走 OpenMontage 的 animated-explainer 管线出一条 9:16、<60 秒的竖屏视频：
> 一只可爱卡通猫厨师教做番茄炒蛋。旁白和字幕的用量/火候/时长必须逐字来自 recipe.json。
> 出图暂时用免费方案（无 key 时 Remotion 纯动效 + 占位图也可），先验证全链路能出片。

第一条片的目标是**验证链路**，不是最终画质。画质在 P2（LoRA + 分镜模板）解决。

## 4. 2070Ti 机器（P2 前置，可并行做）

1. 装 [Stable Diffusion WebUI](https://github.com/AUTOMATIC1111/stable-diffusion-webui)（`--api --medvram` 启动）或 ComfyUI。
2. 猫主角定妆：先用 SDXL 生成 30-50 张候选猫厨师形象，挑一组风格一致的作为 LoRA 训练集。
3. LoRA 训练用 kohya_ss 低显存配置（8GB 可行），或云端租 GPU 训一次（~$2-5）。

## 5. 需要申请/准备的账号材料

| 项目 | 用途 | 时机 |
|---|---|---|
| DeepSeek API key | 生产文案 | P3 前 |
| Azure 资源组 maomao-dev（Storage 账户 + Speech 服务） | 队列/表/TTS | P3 前 |
| Bark App（iPhone）或 Telegram bot | 手机告警 | P3 前 |
| B站账号 cookie（biliup 扫码登录） | 上传 | P4，只配在 prod |

## 完成判据（P1 出口）

- [ ] repo 在 GitHub，main 受保护，CI 绿
- [ ] Mac mini 能跑 `pytest` 全过
- [ ] 出了一条完整的番茄炒蛋竖屏视频（画质不限），旁白用量与 recipe.json 逐项一致
- [ ] 你看完视频，确认"照着做能还原"——这是整个产品的立身之本
