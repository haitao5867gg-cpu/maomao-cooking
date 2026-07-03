# 猫猫炒菜 — 2070Ti 出图机引导脚本（Windows 10/11）
# 用法：右键"使用 PowerShell 运行"，或：
#   powershell -ExecutionPolicy Bypass -File worker\gpu\setup_gpu.ps1
# 作用：装依赖 → 拉取 SD WebUI → 下载 SDXL 模型(~6.9GB) → 用 8GB 显存参数启动
# 幂等：已完成的步骤自动跳过，中断后重跑即可。

$ErrorActionPreference = "Stop"
$WebuiDir = "$env:USERPROFILE\stable-diffusion-webui"
$ModelUrl = "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors"
$ModelPath = "$WebuiDir\models\Stable-diffusion\sd_xl_base_1.0.safetensors"

Write-Host "== [1/5] 检查显卡 ==" -ForegroundColor Cyan
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
if ($LASTEXITCODE -ne 0) { throw "nvidia-smi 失败，请先装 NVIDIA 驱动" }

Write-Host "== [2/5] 安装 Git 与 Python 3.10（已装则跳过）==" -ForegroundColor Cyan
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { winget install --id Git.Git -e --accept-package-agreements --accept-source-agreements }
$py310 = "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe"
if (-not (Test-Path $py310)) { winget install --id Python.Python.3.10 -e --accept-package-agreements --accept-source-agreements }

Write-Host "== [3/5] 拉取 Stable Diffusion WebUI ==" -ForegroundColor Cyan
if (-not (Test-Path $WebuiDir)) { git clone --depth 1 https://github.com/AUTOMATIC1111/stable-diffusion-webui.git $WebuiDir }

Write-Host "== [4/5] 下载 SDXL base 模型（~6.9GB，可断点续传）==" -ForegroundColor Cyan
if (-not (Test-Path $ModelPath) -or (Get-Item $ModelPath).Length -lt 6GB) {
    curl.exe -L -C - -o $ModelPath $ModelUrl
}

Write-Host "== [5/5] 写入 8GB 显存启动参数并启动 ==" -ForegroundColor Cyan
# --medvram-sdxl: 8GB 显存必需  --no-half-vae: 避免 20 系显卡出黑图  --api: 供出图脚本调用
$args8g = 'set COMMANDLINE_ARGS=--api --medvram-sdxl --no-half-vae --xformers'
$bat = Get-Content "$WebuiDir\webui-user.bat" -Raw
if ($bat -notmatch "medvram-sdxl") {
    (Get-Content "$WebuiDir\webui-user.bat") -replace '^set COMMANDLINE_ARGS=.*', $args8g | Set-Content "$WebuiDir\webui-user.bat"
}

Write-Host "启动 WebUI（首次启动会自动装 PyTorch 等，约 10-20 分钟）..." -ForegroundColor Green
Write-Host "看到 'Running on local URL: http://127.0.0.1:7860' 即就绪，浏览器可打开测试。" -ForegroundColor Green
Set-Location $WebuiDir
.\webui-user.bat
