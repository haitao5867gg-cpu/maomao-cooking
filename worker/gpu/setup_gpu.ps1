# maomao-cooking - GPU worker bootstrap (Windows 10/11, ASCII-only for PS 5.1 GBK console)
# Usage: powershell -ExecutionPolicy Bypass -File worker\gpu\setup_gpu.ps1
# Steps: deps -> SD WebUI -> venv fixup -> SDXL model (~6.9GB) -> launch
# Idempotent: finished steps are skipped; safe to re-run after interruption.
# China-network-aware: uses hf-mirror, pypi tuna mirror, gitcode mirrors.

$ErrorActionPreference = "Stop"
$WebuiDir = "$env:USERPROFILE\stable-diffusion-webui"
$ModelUrl = "https://hf-mirror.com/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors"
$ModelUrlFallback = "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors"
$ModelPath = "$WebuiDir\models\Stable-diffusion\sd_xl_base_1.0.safetensors"
$PipMirror = "https://pypi.tuna.tsinghua.edu.cn/simple"
$py310 = "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe"

# ── 1. GPU ──
Write-Host "== [1/7] Check GPU ==" -ForegroundColor Cyan
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
if ($LASTEXITCODE -ne 0) { throw "nvidia-smi failed - install NVIDIA driver first" }

# ── 2. Git + Python ──
Write-Host "== [2/7] Install Git + Python 3.10 (skip if present) ==" -ForegroundColor Cyan
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    winget install --id Git.Git -e --accept-package-agreements --accept-source-agreements
}
if (-not (Test-Path $py310)) {
    winget install --id Python.Python.3.10 -e --accept-package-agreements --accept-source-agreements
}

# ── 3. Clone WebUI ──
Write-Host "== [3/7] Clone Stable Diffusion WebUI ==" -ForegroundColor Cyan
if (-not (Test-Path $WebuiDir)) {
    git clone --depth 1 https://github.com/AUTOMATIC1111/stable-diffusion-webui.git $WebuiDir
}

# ── 4. Create venv + fix pip infrastructure BEFORE first launch ──
Write-Host "== [4/7] Setup venv + pip infrastructure ==" -ForegroundColor Cyan
$Venv = "$WebuiDir\venv\Scripts\python.exe"
if (-not (Test-Path $Venv)) {
    & $py310 -m venv "$WebuiDir\venv"
}
& $Venv -m pip install --upgrade pip -i $PipMirror --quiet
& $Venv -m pip install "setuptools==70.0" wheel -i $PipMirror --quiet
Write-Host "  OK: pip + setuptools 70.0 + wheel"

# Pre-install packages that WebUI's launcher struggles with in China
Write-Host "  Pre-installing PyTorch 2.1.2+cu121..."
$hasTorch = & $Venv -c "import torch; print('yes')" 2>$null
if ($hasTorch -ne "yes") {
    & $Venv -m pip install torch==2.1.2 torchvision==0.16.2 --index-url https://download.pytorch.org/whl/cu121
}

Write-Host "  Pre-installing CLIP, open_clip, xformers..."
$hasClip = & $Venv -c "import clip; print('yes')" 2>$null
if ($hasClip -ne "yes") {
    & $Venv -m pip install --no-build-isolation https://github.com/openai/CLIP/archive/d50d76daa670286dd6cacf3bcd80b5e4823fc8e1.zip --quiet
}
$hasOpenClip = & $Venv -c "import open_clip; print('yes')" 2>$null
if ($hasOpenClip -ne "yes") {
    & $Venv -m pip install open_clip_torch -i $PipMirror --quiet
}
$hasXformers = & $Venv -c "import xformers; print('yes')" 2>$null
if ($hasXformers -ne "yes") {
    & $Venv -m pip install xformers==0.0.23.post1 --no-deps -i $PipMirror
}

# ── 5. Clone repos that Stability-AI removed from GitHub ──
Write-Host "== [5/7] Clone required repositories ==" -ForegroundColor Cyan

$repos = @(
    @{ Name = "stable-diffusion-stability-ai"; Url = "https://gitcode.com/Stability-AI/stablediffusion.git" },
    @{ Name = "generative-models";             Url = "https://gitcode.com/Stability-AI/generative-models.git" },
    @{ Name = "k-diffusion";                   Url = "https://github.com/crowsonkb/k-diffusion.git" },
    @{ Name = "BLIP";                          Url = "https://github.com/salesforce/BLIP.git" },
    @{ Name = "stable-diffusion-webui-assets";  Url = "https://github.com/AUTOMATIC1111/stable-diffusion-webui-assets.git" }
)

foreach ($repo in $repos) {
    $repoDir = "$WebuiDir\repositories\$($repo.Name)"
    if (-not (Test-Path "$repoDir\.git")) {
        Write-Host "  Cloning $($repo.Name)..."
        git clone --depth 1 $repo.Url $repoDir
    } else {
        Write-Host "  $($repo.Name): OK"
    }
}

# ── 6. Download SDXL model ──
Write-Host "== [6/7] Download SDXL base model (~6.9GB, resumable) ==" -ForegroundColor Cyan
if (-not (Test-Path $ModelPath) -or (Get-Item $ModelPath).Length -lt 6GB) {
    curl.exe -L -C - -o $ModelPath $ModelUrl
    if ($LASTEXITCODE -ne 0) { curl.exe -L -C - -o $ModelPath $ModelUrlFallback }
} else {
    Write-Host "  OK: model already downloaded"
}

# ── 7. Write launch config ──
Write-Host "== [7/7] Write launch config + start ==" -ForegroundColor Cyan

$batContent = @"
@echo off
set PYTHON=$py310
set GIT=
set VENV_DIR=
set COMMANDLINE_ARGS=--api --medvram-sdxl --no-half-vae --xformers --skip-torch-cuda-test --skip-git
call webui.bat
"@

Set-Content "$WebuiDir\webui-user.bat" $batContent -Encoding ASCII

Write-Host "Starting WebUI..." -ForegroundColor Green
Write-Host "Ready when you see: Running on local URL: http://127.0.0.1:7860" -ForegroundColor Green
Set-Location $WebuiDir
.\webui-user.bat
