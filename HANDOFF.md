# HANDOFF — 跨机器 session 交接（2026-07-05 晚 最终更新）

> 新 session 第一步：读本文件 + CLAUDE.md + ARCHITECTURE.md。本文件记录"文档还没来得及沉淀"的实时状态。

## 当前状态（P2：候选图已完成，待筛选）

- **batch03 已跑完**：3 风格（A_3d_pixar / B_flat_kawaii / C_ghibli_soft）× 12 seed = 36 张，在 Blob `dev-gpu-output` 容器 `gpu-output/candidates-batch03/`。基线 prompt 见本文件末尾附录（~60 token，勿超 CLIP 77）。
- **全链路验证全绿**：布偶猫单场景测试（`gpu-output/test-ragdoll-001/ragdoll_seed42.png`）无警告无报错，速度 ~4s/it（fp16-fix VAE 生效）。
- **接手后第一件事：从 Blob 拉 batch03 的 36 张图给用户筛选** → 定画风+seed 基线 → LoRA 训练集 → 分镜模板。i2v 路线下优先推荐 A 组（3D）。
- **发 GPU 任务的标准方式**（勿再用 Portal 手点）：写 JSON 到 `jobs/*.json`（格式参考 `jobs/test-ragdoll.json`），用户在 Mac 终端跑：
  `cd <仓库目录> && .venv/bin/python3 worker/send_job.py jobs/xxx.json`

## 重大决策（尚未写入 ARCHITECTURE.md，待办）

- **动画路线已改**：全片用即梦/可灵网页版（用户只有会员无 API）做图生视频。SDXL+LoRA 只出每镜**首帧**，Remotion 降级为拼接层（字幕/BGM/TTS）。管线需设计"人工 i2v 工位"：自动打包首帧+运动 prompt → 用户手动上传下载 → 回投文件夹继续自动。
- i2v 画风优先 3D（A 组），flat 2D 最易在 i2v 中扭曲。
- 运动 prompt 只描述动作/镜头，不重复外观（重复会诱导 i2v 重画角色）。

## 踩坑记录（新增，旧坑见仓库内文档）

1. **队列消息必须纯文本 JSON**：Portal"添加消息"弹窗默认勾选 Base64，必须取消勾选！worker 直接 `json.loads(msg.content)` 不解码。弹窗会记住上次勾选状态，每次发消息前确认。
2. **2070Ti 新开 PowerShell 丢环境变量**：需要 `HF_HOME=E:\SDXLModel`、`HF_ENDPOINT=https://hf-mirror.com`。已用 `[Environment]::SetEnvironmentVariable(...,"User")` 永久写入，但从旧窗口/双击启动的进程可能拿不到，启动 bat 前最好显式 `$env:` 设一遍。
3. **fp16-fix VAE**（`madebyollin/sdxl-vae-fp16-fix`）修复 8GB 显存溢出降速 3.6 倍的问题（commit fcf4627），但 2070Ti 走 hf-mirror 的 hf_hub 下载链路失败，代码已加保底：下载失败退回官方 VAE（慢但能跑，commit 60af4df）。可手动下载 VAE 两个文件到 `E:\SDXLModel\sdxl-vae-fp16-fix\` 并设 `MAOMAO_SD_VAE` 指向该目录提速。
4. **12 场景批次耗时 > 队列 600s visibility timeout**：消息会中途重新可见。单 worker 无碍；以后多 worker 要改心跳续期。
5. GPU 作业 JSON 格式见 `worker/test_send_job.py`；幂等：`{scene_id}.png` 已存在则跳过（断点续跑靠这个）。

## 各机器角色（不变）

- **Mac mini**：编排/渲染/上传，`.venv` + `~/.env-maomao`（Azure 连接串）。
- **2070Ti Windows**（E:\maomao-cooking，用户名 13421）：无头 GPU worker，`worker\gpu\setup\start-gpu-worker.bat` 启动。国内网络，HF 走 hf-mirror。
- **Cowork 开发机**（本文档的读者）：只做开发迭代，通过 git + Azure Portal（Chrome）+ 队列消息驱动一切。沙箱不能直连 Azure 数据面/HF/api.github.com。

## 新机器接手清单

1. 让用户提供 GitHub fine-grained PAT（名为 `claude-maomao`，仅本仓库 Contents 读写，2026-07-03 创建约 90 天有效）→ 存入本机 memory，**绝不写进 git**（铁律 #6）。
2. git 推送方法：沙箱内 `/tmp` 克隆中转（挂载目录 .git 只读）：`git clone https://x-access-token:<PAT>@github.com/haitao5867gg-cpu/maomao-cooking.git`。
3. 队列/Blob 操作：用 Claude in Chrome 打开用户已登录的 Azure Portal（订阅 a61796b5-…，资源组 maomao-dev，存储账户 maomaodevstore）。
4. 当前工作分支：`feature/p2-gpu-worker`（main 受保护需 PR+CI）。
5. 用户偏好：中文、极简直接、能自动就自动、给他的手动步骤压到最少；所有 Azure 操作完成后更新 CLAUDE.md/memory/git。

## 附录：batch03 基线 prompt

```
正向（角色部分，~54 token）:
cute orange tabby cat chef, chibi proportions, short stubby limbs, round chubby face,
big amber eyes, white muzzle and paws, white chef hat, red apron, smiling,
holding wooden spatula, front view, upper body, plain pastel background

风格词:
A: 3D render, pixar style, soft lighting, vibrant colors
B: flat 2D kawaii illustration, thick outlines, pastel colors, sticker style
C: ghibli style anime, watercolor shading, warm light, storybook illustration

负向:
realistic photo, human, human hands, human fingers, deformed, extra limbs, extra tails,
multiple cats, bad anatomy, mutated paws, lowres, text, watermark, blurry, dark, scary, ugly

参数: 832×1216, steps 28, cfg 6.5, seeds [42,101,202,303,404,505,606,707,808,909,1234,5678]
```
