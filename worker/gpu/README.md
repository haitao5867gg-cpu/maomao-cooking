# worker/gpu — 2070Ti 出图机操作指南（P2）

不装 Claude Code 的协作方式：**你跑脚本 → git push 结果 → Mac 上的 Claude 分析并给下一步**。

## 第一次设置（一次性，总共 4 条命令）

在 2070Ti 电脑的 PowerShell 里：

```powershell
# 1. clone 仓库（没装 git 的话先 winget install Git.Git）
git clone https://github.com/haitao5867gg-cpu/maomao-cooking.git
cd maomao-cooking

# 2. 引导脚本：装依赖 + SD WebUI + SDXL 模型(~6.9GB) + 启动
#    首次跑 30-60 分钟（主要是下载），中断可重跑
powershell -ExecutionPolicy Bypass -File worker\gpu\setup_gpu.ps1
```

看到 `Running on local URL: http://127.0.0.1:7860` 即就绪（这个窗口保持开着）。

## 生成猫主角候选图（新开一个 PowerShell 窗口）

```powershell
cd maomao-cooking
pip install requests pillow
python worker\gpu\generate_candidates.py    # 36 张，约 30-50 分钟
```

## 把结果推回来

```powershell
git checkout -b p2-cat-candidates
git add assets/candidates
git commit -m "P2: 猫主角候选图 batch01"
git push -u origin p2-cat-candidates
```

推完回到 Mac 上告诉 Claude"候选图推上去了"，它会拉下来帮你筛选、迭代 prompt，
选定后它准备 LoRA 训练脚本（同样是你跑一条命令）。

## 常见问题

- **出黑图**：确认启动参数含 `--no-half-vae`（setup 脚本已写入）。
- **显存不足 (CUDA out of memory)**：确认含 `--medvram-sdxl`；关闭其他占显存程序。
- **每张图耗时**：8GB 显存 SDXL 约 40-90 秒/张，属正常。
- **想中途看效果**：浏览器开 http://127.0.0.1:7860 手动玩，不影响脚本。
