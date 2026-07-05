# CLAUDE.md — 猫猫炒菜 系统操作契约

你正在迭代"猫猫炒菜"：全自动动画猫美食短视频系统。**动手前先读 [ARCHITECTURE.md](ARCHITECTURE.md)。**

## 系统一句话

真实菜谱 → recipe.json → 猫主角出图(2070Ti/SDXL+LoRA) → 中文TTS(Azure) → Remotion 合成竖屏<60s → biliup 上传B站 → 每日拉播放数据。任务经 Azure Storage Queue 分发，两台机器（Mac mini=编排/渲染/上传，2070Ti=出图）出站轮询领活。

## 铁律（违反 = 破坏生产）

1. **只在 feature 分支工作，永不直接改 main。** PR 须 CI 全绿。生产机器只运行 release tag。
2. **prod 资源（maomao-prod 资源组、B站 cookie）绝不在开发中触碰。** dev/staging 物理上没有上传凭据，保持这个设计。
3. **旁白/字幕文案只能从 recipe.json 生成**，禁止 LLM 即兴补充用量、火候、时长——用户会照着做菜，幻觉=翻车。
4. **生产管线是确定性脚本**（worker/stages/），不引入自由发挥的 agent 循环。Agent（你）只用于开发迭代。
5. **Table Storage schema 只加列不改列**（保证 tag 回滚后旧代码可读）。
6. 密钥只走 .env / Azure Key Vault，任何密钥、cookie、连接串不进 git。

## 模块地图

| 目录 | 职责 |
|---|---|
| `openmontage/` | 子模块（AGPL-3.0）。工具库+Remotion 模板来源，勿改其内部，用包装层 |
| `worker/` | 队列轮询框架 + `stages/`（幂等管线阶段）+ `gpu/`（2070Ti 无头 worker：diffusers 直接推理，不用 WebUI） |
| `recipe/` | 菜谱抓取、结构化、校验。`schema/recipe.schema.json` 是全系统契约 |
| `llm/` | LLM 网关（OpenAI 兼容，DeepSeek/Foundry 切换）+ prompt 模板 |
| `uploader/` | biliup 封装 + 失败降级（存Blob+面板卡片+告警） |
| `analytics/` | B站播放数据拉取入库 |
| `dashboard/` | Azure Static Web Apps 面板 + Functions API |
| `infra/` | Azure 部署脚本 + bicep，env 参数部署 maomao-{dev,staging,prod} 三资源组 |
| `assets/` | 猫 LoRA 指针、姿势模板、分镜模板、BGM 库 |

## Azure 资源清单（dev 环境）

| 资源类型 | 名称 | 资源组 | 区域 | 备注 |
|---|---|---|---|---|
| 资源组 | `maomao-dev` | — | East Asia | 所有 dev 资源的容器 |
| 存储账户 | `maomaodevstore` | maomao-dev | East Asia | Standard_LRS, StorageV2 |
| Speech 服务 | `maomao-speech-dev` | maomao-dev | East Asia | F0 免费层，中文 TTS |
| 队列 | `dev-gpu-jobs` | maomaodevstore | — | GPU 出图作业队列 |
| 队列 | `dev-gpu-jobs-poison` | maomaodevstore | — | GPU 作业死信队列 |
| 队列 | `dev-pipeline-jobs` | maomaodevstore | — | Mac 编排管线队列 |
| Blob 容器 | `dev-gpu-output` | maomaodevstore | — | GPU 生成的图片 |
| Blob 容器 | `dev-videos` | maomaodevstore | — | 成品视频归档 |
| Table | `devtasks` | maomaodevstore | — | 任务状态表（worker 首次运行自动创建） |

> 连接串存于各机器本地 `.env-maomao`，**不进 git**（铁律 #6）。
> staging/prod 环境资源命名规则相同，前缀分别为 `staging-` / `prod-`，存储账户分别为 `maomaostagingstore` / `maomaoprodstore`。

## 关键约定

- 环境由 `MAOMAO_ENV`（dev/staging/prod）决定，队列/表名自动加前缀。
- 每个 stage：输入输出走任务工作目录 `projects/<video-id>/`，可重复执行（幂等），完成后回写任务表。
- 角色一致性三件套：`CAT_LORA_NAME` + `CAT_BASE_SEED` + `assets/poses/` ControlNet 姿势模板，不要绕过。
- 视频节奏模板：钩子(3s)→食材卡(5s)→步骤×N(4-8s/步，常驻用量字幕条)→成品+配料表(5s)，分镜模板在 `assets/storyboards/`。
- 测试：`pytest tests/`；schema 改动必须同步更新金样本 `recipe/samples/` 和测试。

## 当前状态（每次重大变更后更新此节）

- 2026-07-03：P1 完成——管线五阶段(worker/stages/)就绪，首条番茄炒蛋验证片 QC 全绿(57.2s)。Azure maomao-dev 资源组 + F0 Speech 已建。
- 2026-07-04：P2 GPU Worker 架构确定——2070Ti 改为无头节点，diffusers 直接推理（不用 A1111/ComfyUI WebUI），通过 Azure Queue 自主领活。网络模型：2070Ti 裸连家庭宽带（不需 VPN），只做出站 HTTPS 到 Azure；Mac 和 2070Ti 物理上互不可见不影响生产。详见 ARCHITECTURE.md "GPU Worker 架构" 章节。
- 2026-07-04：Azure Storage 账户 `maomaodevstore` 已创建（East Asia, Standard_LRS），队列（dev-gpu-jobs / poison / pipeline-jobs）和 Blob 容器（dev-gpu-output / dev-videos）就绪。部署脚本 `infra/setup-dev-storage.sh`。
- 2026-07-05：**P2 GPU Worker 端到端验证通过**——从 Azure Portal 手动往 dev-gpu-jobs 发测试任务，2070Ti worker 自动领取、SDXL 推理（28步/1分43秒）、上传图片到 dev-gpu-output Blob（`gpu-output/test-001/00_test.png`, 1.11MiB）、回写任务表。全链路无人工干预。Mac .venv 已建好（python3 + azure-storage-queue 等依赖）。
