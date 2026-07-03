# 猫猫炒菜 — 全自动动画美食视频系统 设计方案 v2

> 一只动画猫做美食的竖屏短视频（<60秒），基于真实菜谱、可一比一还原。
> 全流程自动化：选题 → 制作 → 渲染 → 上传B站 → 拉取播放数据 → 数据分析。
> 云端面板随时查看系统状态。系统本身上 git，任何机器的 Claude 都能迭代。

## 已确定的决策

| 决策点 | 选择 |
|---|---|
| 制作核心 | OpenMontage（子模块）：P1 用其 agent 管线探索，之后固化为确定性脚本，降级为工具库 + Remotion 模板来源 |
| 动画形式 | 本地出图（SD/SDXL + 猫主角 LoRA + 固定 seed + ControlNet 姿势库）+ Remotion 动效合成 |
| 视频形态 | 竖屏 9:16，<60 秒，一道菜一条视频 |
| 发布平台 | B站（biliup 上传，非官方接口拉数据，含手动发布降级路径） |
| LLM 策略 | 开发/迭代 = 现有 Claude 订阅（headless Claude Code）；生产文案 = DeepSeek API 直连（夜间避峰）；备用 = Azure AI Foundry。统一 LLM 网关配置（base_url + key），换供应商改一行 |
| 任务队列 | Azure Storage Queue，两台机器出站轮询领活（拉取模式，机器间零耦合） |
| 状态面板 | Azure Static Web Apps（免费层）+ Functions 消费计划 + Table Storage，成本 ≈ $0 |
| 本地算力 | 2070Ti 机器 = 无头 GPU worker（diffusers 直接推理，不装 WebUI）；Mac mini = 编排/渲染/上传 worker，均 24h 运行 |
| GPU 推理 | diffusers + safetensors 直接加载 SDXL+LoRA，不经过 A1111/ComfyUI——8GB 显存零浪费，无需 Web 服务进程 |

## 核心架构原则

1. **生产的可靠性来自确定性，不来自智能。** Agent（Claude Code）只用于开发和迭代系统；生产管线是固化的 Python 脚本，LLM 仅在固定节点被模板化调用（菜谱结构化、文案、出图 prompt）。
2. **机器间零耦合。** 所有机器只做出站连接（轮询 Azure 队列、上报状态），不开端口、不依赖内网连通。任一台重启不影响另一台，未来加 worker 即插即用。
3. **单一事实来源。** 任务状态、内容日历、播放数据全部在 Azure Table Storage；面板直接读它，不另做心跳上报机制。
4. **内容排期与生产解耦。** 调研批量产出 backlog，生产按日历消费，互不阻塞。
5. **每一步幂等、可断点续跑、失败有告警、上传有降级。** 静默死亡不可接受。

## 系统架构

```
┌────────────────────────── Azure（云端，≈$0-3/月）──────────────────────────┐
│  Static Web Apps + Functions：状态面板（任务/日历/播放数据图表/待手动发布卡片）│
│  Storage Queue：任务队列（stage 粒度）+ 死信队列                             │
│  Table Storage：任务表 / 内容日历(recipe backlog) / 视频表 / 每日播放数据     │
│  Blob Storage：成品视频+封面归档（30天转冷层）                               │
│  Azure Speech TTS：中文配音（免费额度 50万字符/月）                          │
│  Key Vault：API keys、biliup cookie                                        │
└──────────────▲───────────────────────────────▲────────────────────────────┘
        出站轮询│领活+回写状态                    │出站轮询领活+回写状态
┌──────────────┴──────────────┐  ┌─────────────┴──────────────┐
│ Mac mini（编排+渲染 worker）  │  │ 2070Ti 机器（无头 GPU worker）│
│ · 调度器（内容日历→当日任务）  │  │ · 无显示器、无 WebUI          │
│ · 菜谱调研+结构化+校验(批量)   │  │ · diffusers 直接推理          │
│ · DeepSeek 文案生成(夜间避峰) │  │   SDXL+猫LoRA 批量出图        │
│ · Remotion 渲染 (9:16)       │  │   (模型常驻 VRAM，跨任务复用)  │
│ · biliup 上传（含降级）       │  │ · ControlNet 姿势模板         │
│ · 每日拉取 B站播放数据         │  │ · Real-ESRGAN 超分            │
│ · 告警推送                    │  │ · systemd 守护进程，开机自启   │
└─────────────────────────────┘  └─────────────────────────────┘
                                     告警(Telegram/Bark)→手机：
                                     job卡住>2h / worker掉线>10min
                                     / 上传失败 / cookie失效
```

## 内容流水线

**调研线（每周批量，与生产解耦）**：选题池 → 联网搜真实菜谱（交叉比对 2-3 个来源）→ 结构化为 `recipe.json`（食材精确用量、步骤、火候、每步时长）→ 自动校验（单位统一/步骤完整/时长合理）→ 入内容日历，维持 20-30 条已校验 backlog。可在面板预览和调整排期。

**生产线（每日自动，单条视频）**：

1. 从内容日历取当日 recipe.json。
2. 文案生成（DeepSeek，模板化 prompt）：旁白+字幕**只能**从 recipe.json 生成，禁止即兴。<60s 节奏：钩子(3s) → 食材卡(5s) → 步骤×N(每步4-8s，常驻用量/火候字幕条) → 成品+完整配料表(5s)。
3. 出图任务入队 → 2070Ti 领活：猫 LoRA + 固定 seed + 姿势模板出图，食材/器具须可辨认。
4. Azure TTS 配音。
5. Remotion 合成（3-5 套分镜模板轮换 + BGM/转场随机化，防同质化）。
6. 质检：ffprobe/抽帧/音频电平（复用 OpenMontage self-review）+ 菜谱一致性 diff（字幕用量 vs recipe.json 逐项比对）。
7. 上传 B站（biliup，标题/简介含文字版完整菜谱/标签/封面）。**降级**：失败→成品存 Blob→面板出"待手动发布"卡片→手机告警，生产不停。
8. 每日拉取播放/点赞/投币/收藏/弹幕 → Table Storage → 面板图表。

**可靠性**：每阶段幂等+checkpoint 可续跑；失败重试 2 次后进死信队列并告警；起号初期开"上传前人工确认"开关，稳定后关闭。

## 仓库结构（GitHub 私有仓库）

```
maomao-cooking/
├── CLAUDE.md              # 系统全貌+操作契约，任何机器的 Claude 直接接手
├── ARCHITECTURE.md        # 本文档
├── openmontage/           # 子模块（AGPL-3.0，自用无碍）
├── worker/                # 统一 worker 框架：轮询队列、领活、回写、告警
│   ├── stages/            # 固化的管线阶段（幂等脚本）
│   └── gpu/               # 出图/超分（2070Ti 运行）
├── recipe/                # 菜谱抓取、结构化、校验、recipe.json schema
├── llm/                   # LLM 网关（DeepSeek/Foundry/Claude 可切换）+ prompt 模板
├── uploader/              # biliup 封装 + 降级逻辑
├── analytics/             # B站数据拉取 + 入库
├── dashboard/             # Static Web App 前端 + Functions API
├── infra/                 # Azure IaC（bicep）
├── assets/                # 猫主角 LoRA、姿势模板、分镜模板、BGM 库
└── projects/              # 每条视频工作目录（gitignore，本地留 7 天）
```

## GPU Worker 架构（2070Ti 无头节点）

### 设计决策

**选 diffusers 直接推理，不用 A1111/ComfyUI。** 理由：

1. **显存优先**：8GB VRAM，WebUI 进程本身占 200-400MB 开销，diffusers 零浪费。
2. **确定性**：pin `diffusers==x.y.z`，没有 WebUI 升级/插件冲突的风险。项目铁律"生产的可靠性来自确定性"。
3. **无头部署**：不需要 Web 服务器进程、不开端口、不需要显示器。`pip install` + systemd 即完成部署。
4. **模型常驻**：worker 进程持续运行，SDXL+LoRA 加载一次常驻 VRAM，跨任务复用，省去每次冷启动 30-60s。

### 网络模型

2070Ti **不需要 VPN**，只需家庭宽带的出站 HTTPS：

```
2070Ti ──HTTPS──→ Azure Storage Queue（轮询领活）
       ──HTTPS──→ Azure Blob Storage（上传生成结果）
       ──HTTPS──→ Azure Table Storage（回写任务状态）
       ──本地───→ 127.0.0.1（diffusers 推理，无网络端口）
```

Mac 和 2070Ti 物理上互不可见也不影响生产。偶尔维护时，Mac VPN 开 split tunnel 可 SSH 到 2070Ti 局域网 IP。

### 模块结构

```
worker/gpu/
├── worker_loop.py          # 主循环：轮询队列 → 调推理 → 上传结果 → 回写状态
├── inference.py            # diffusers 封装：模型加载、LoRA 注入、批量生图
├── generate_candidates.py  # P2 候选图生成（角色定型用，复用 inference.py）
└── setup/
    ├── requirements-gpu.txt       # 2070Ti Python 依赖（torch/diffusers/azure-storage/...）
    ├── start-gpu-worker.bat       # Windows 启动脚本（含崩溃自动重启循环）
    ├── install-task-scheduler.bat # 注册 Windows 任务计划（开机自启）
    └── gpu-worker.service         # Linux systemd unit（备用）
```

### 队列消息格式（GPU 作业）

Mac 编排器往 `{env}-gpu-jobs` 队列发消息，2070Ti worker 领取执行：

```json
{
  "video_id": "tomato-egg-001",
  "job_type": "scene_batch",
  "scenes": [
    {
      "scene_id": "00_hook",
      "prompt": "cute orange tabby cat chef, round chubby face, big amber eyes, white chef hat, red apron, happy expression, holding tomato, cozy kitchen background",
      "negative_prompt": "realistic photo, human, deformed, extra limbs, text, watermark, blurry",
      "seed": 42,
      "width": 832,
      "height": 1216,
      "steps": 28,
      "cfg_scale": 6.5
    }
  ],
  "lora": {"name": "maomao-v1", "weight": 0.8},
  "controlnet_pose": "assets/poses/holding_item.png",
  "output_blob_prefix": "gpu-output/tomato-egg-001/"
}
```

### Worker 主循环

```
启动 → 加载 SDXL+LoRA 到 VRAM（一次性，常驻）
  ↓
轮询 {env}-gpu-jobs 队列（30s 间隔，无消息时空转）
  ↓
领取消息 → 解析作业 → 逐场景推理 → 本地暂存 PNG
  ↓
批量上传 Blob Storage → 回写 Table Storage（video_id, stage=gpu, status=done）
  ↓
删除队列消息 → 回到轮询
```

失败处理：单场景推理失败重试 2 次 → 整条作业进死信队列 `{env}-gpu-jobs-poison` → 告警。

### 2070Ti 部署（一次性，Windows）

```powershell
# 1. 克隆仓库到 C:\maomao-cooking
git clone <repo> C:\maomao-cooking
cd C:\maomao-cooking
git checkout feature/p2-gpu-worker

# 2. 安装 PyTorch（CUDA 12.x）+ 项目依赖
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
pip install -r worker\gpu\setup\requirements-gpu.txt

# 3. 环境变量（创建 %USERPROFILE%\.env-maomao）
# 写入两行：
#   AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...
#   MAOMAO_ENV=dev

# 4. 下载 SDXL 模型（首次约 6GB，需几分钟）
python -m worker.gpu.inference --download-model

# 5. 注册开机自启（管理员身份运行）
worker\gpu\setup\install-task-scheduler.bat

# 6. 首次手动启动
worker\gpu\setup\start-gpu-worker.bat

# 完成。此后不需要登录这台机器。
# 更新代码：远程桌面 → git pull → 重启 start-gpu-worker.bat
```

## 多环境与发布工程（保护 prod 的三道闸）

**铁律：未验证的代码永远碰不到 prod。生产机器只运行 release tag，不追 main。**

| 环境 | Azure 资源组 | 用途 | 上传能力 |
|---|---|---|---|
| dev | maomao-dev | 任何机器上的 Claude 开发迭代，LLM/上传全 mock | 无（无凭据） |
| staging | maomao-staging | 影子生产：新版本真实跑 1-2 条完整视频，成品进面板"待审"，人工看片 | 无（无凭据） |
| prod | maomao-prod | 正式运行 | biliup cookie 仅存于 prod Key Vault |

- **分支策略**：main 受保护；Claude 只在 feature 分支工作 → PR → CI 全绿 → 合并；发布 = 打 tag；回滚 = 指回上一 tag（一条命令，保留最近 N 个版本）。
- **CI 质量门（GitHub Actions）**：单元测试 + recipe.json schema 契约测试 + lint + 金样本端到端测试（固定 recipe fixture 走完整管线，LLM 用录制 fixture、上传 mock，ffprobe 校验产物）。
- **环境隔离**：同一套 bicep 传 env 参数部署三个资源组，队列/表/Blob 天然隔离；dev/staging 物理上没有 B站凭据，误发不可能发生。
- **Staging 影子运行**：两台机器的 worker 各多起一个 staging 进程吃 staging 队列。新版本先出 1-2 条影子片，面板看片确认后才 promote prod tag。
- **金丝雀 + 自动回滚**：prod 新版本第一条视频暂停在上传前等人工确认；部署后连续 2 条管线失败 → worker 自动回退上一 tag + 手机告警。
- **数据面保护**：Table Storage 每日快照到 Blob；schema 只加列不改列，保证回滚后旧代码仍能读数据。

## 成本估算

| 项目 | 成本 |
|---|---|
| 出图/渲染/上传 | ¥0（全本地） |
| Azure（面板+队列+表+Blob+TTS） | ≈ $0-3/月（基本全在免费额度内） |
| DeepSeek 文案（夜间平价时段） | ≈ ¥0.05-0.2/条视频 |
| 开发迭代 LLM | ¥0（现有 Claude 订阅） |
| 猫 LoRA 训练（一次性） | 本地低显存模式可行；或云端租 GPU 训一次 ~$2-5 |

## 主要风险

1. **B站非官方接口失效**（何时而非是否）：告警+降级手动发布兜底；上传频率保持自然（每日 1-2 条）；cookie 失效当天可知。
2. **8GB 显存**：SDXL 出图 OK；LoRA 训练用低显存配置或云端训一次；不做本地 AI 视频生成。
3. **菜谱准确性**（LLM 幻觉=用户做菜翻车）：真实来源交叉比对 → 结构化 JSON → 文案只从 JSON 生成 → 一致性 diff 质检，四道闸。
4. **Mac mini 单点**：业余规模可接受；repo+IaC 可重建，成品在 Blob 不丢。

## 实施阶段

- **P1 跑通单条**：repo 脚手架（含 CI 骨架 + main 分支保护）+ OpenMontage 安装 + 用 Claude Code agent 手动出一条完整视频，验证画风和还原度。
- **P2 角色定型**：猫主角设计 + LoRA 训练 + 固定 seed/姿势库 + 3-5 套分镜模板。
- **P3 管线固化**：把 P1 验证的流程固化为 worker stages + Azure 队列/表（dev/staging/prod 三资源组）+ 两台机器接入 + 金样本 CI 测试。
- **P4 发布闭环**：biliup 上传 + 降级路径 + 告警 + 数据采集。
- **P5 云端可视**：面板（任务/日历/数据图表/手动发布卡片）。
- **P6 迭代运营**：根据播放数据调整选题/节奏/封面，逐步关闭人工确认。
