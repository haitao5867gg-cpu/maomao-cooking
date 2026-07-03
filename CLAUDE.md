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
| `worker/` | 队列轮询框架 + `stages/`（幂等管线阶段）+ `gpu/`（2070Ti 出图/超分） |
| `recipe/` | 菜谱抓取、结构化、校验。`schema/recipe.schema.json` 是全系统契约 |
| `llm/` | LLM 网关（OpenAI 兼容，DeepSeek/Foundry 切换）+ prompt 模板 |
| `uploader/` | biliup 封装 + 失败降级（存Blob+面板卡片+告警） |
| `analytics/` | B站播放数据拉取入库 |
| `dashboard/` | Azure Static Web Apps 面板 + Functions API |
| `infra/` | bicep，env 参数部署 maomao-{dev,staging,prod} 三资源组 |
| `assets/` | 猫 LoRA 指针、姿势模板、分镜模板、BGM 库 |

## 关键约定

- 环境由 `MAOMAO_ENV`（dev/staging/prod）决定，队列/表名自动加前缀。
- 每个 stage：输入输出走任务工作目录 `projects/<video-id>/`，可重复执行（幂等），完成后回写任务表。
- 角色一致性三件套：`CAT_LORA_NAME` + `CAT_BASE_SEED` + `assets/poses/` ControlNet 姿势模板，不要绕过。
- 视频节奏模板：钩子(3s)→食材卡(5s)→步骤×N(4-8s/步，常驻用量字幕条)→成品+配料表(5s)，分镜模板在 `assets/storyboards/`。
- 测试：`pytest tests/`；schema 改动必须同步更新金样本 `recipe/samples/` 和测试。

## 当前状态（每次重大变更后更新此节）

- 2026-07-03：P1 进行中。脚手架已建，schema/金样本/LLM网关/CI 已就绪，尚未出第一条视频。后续见 NEXT_STEPS.md。
