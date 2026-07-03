# maomao-cooking - One-shot WebUI repair for China network environment
# Fixes: setuptools, wheel, CLIP, xformers, missing GitHub repos, launch args
# Usage: powershell -ExecutionPolicy Bypass -File worker\gpu\repair_webui.ps1
# Idempotent: safe to re-run.

$WebuiDir = "$env:USERPROFILE\stable-diffusion-webui"
$Venv = "$WebuiDir\venv\Scripts\python.exe"
$PipMirror = "https://pypi.tuna.tsinghua.edu.cn/simple"
$py310 = "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe"

if (-not (Test-Path $WebuiDir)) { Write-Host "ERROR: WebUI not found at $WebuiDir - run setup_gpu.ps1 first" -ForegroundColor Red; exit 1 }

# ── 1. Ensure venv exists ──
Write-Host "== [1/6] Check venv ==" -ForegroundColor Cyan
if (-not (Test-Path $Venv)) {
    Write-Host "  Creating venv..."
    & $py310 -m venv "$WebuiDir\venv"
}
Write-Host "  OK: $Venv"

# ── 2. Fix pip infrastructure (setuptools + wheel) ──
Write-Host "== [2/6] Fix pip infrastructure ==" -ForegroundColor Cyan
& $Venv -m pip install --upgrade pip -i $PipMirror --quiet 2>&1 | Out-Null
& $Venv -m pip install "setuptools==70.0" wheel -i $PipMirror --quiet 2>&1 | Out-Null
Write-Host "  OK: setuptools 70.0 + wheel"

# ── Helper: check if a Python module is importable ──
function Test-PyModule($module) {
    $output = & $Venv -c "import $module; print('INSTALLED')" 2>&1
    return ($output -match "INSTALLED")
}

# ── 3. Install PyTorch (skip if already present) ──
Write-Host "== [3/6] Check PyTorch ==" -ForegroundColor Cyan
if (Test-PyModule "torch") {
    Write-Host "  OK: PyTorch already installed"
} else {
    Write-Host "  Installing PyTorch 2.1.2+cu121 (2.5GB, be patient)..."
    & $Venv -m pip install torch==2.1.2 torchvision==0.16.2 --index-url https://download.pytorch.org/whl/cu121 2>&1 | ForEach-Object { Write-Host "  $_" }
}

# ── 4. Install CLIP + xformers + open_clip (all from Chinese mirror) ──
Write-Host "== [4/6] Install CLIP, xformers, open_clip ==" -ForegroundColor Cyan

if (Test-PyModule "clip") {
    Write-Host "  OK: CLIP already installed"
} else {
    Write-Host "  Installing CLIP..."
    & $Venv -m pip install --no-build-isolation https://github.com/openai/CLIP/archive/d50d76daa670286dd6cacf3bcd80b5e4823fc8e1.zip --quiet 2>&1 | ForEach-Object { Write-Host "  $_" }
    Write-Host "  OK: CLIP"
}

if (Test-PyModule "open_clip") {
    Write-Host "  OK: open_clip already installed"
} else {
    Write-Host "  Installing open_clip..."
    & $Venv -m pip install open_clip_torch -i $PipMirror --quiet 2>&1 | ForEach-Object { Write-Host "  $_" }
    Write-Host "  OK: open_clip"
}

if (Test-PyModule "xformers") {
    Write-Host "  OK: xformers already installed"
} else {
    Write-Host "  Installing xformers (200MB, may take a few minutes)..."
    & $Venv -m pip install xformers==0.0.23.post1 --no-deps -i $PipMirror 2>&1 | ForEach-Object { Write-Host "  $_" }
    Write-Host "  OK: xformers"
}

# ── 5. Clone missing repos (GitHub repos that Stability-AI deleted) ──
Write-Host "== [5/6] Fix missing repositories ==" -ForegroundColor Cyan

$repos = @(
    @{
        Name = "stable-diffusion-stability-ai"
        Mirrors = @(
            "https://gitcode.com/Stability-AI/stablediffusion.git",
            "https://gitclone.com/github.com/Stability-AI/stablediffusion.git"
        )
    },
    @{
        Name = "generative-models"
        Mirrors = @(
            "https://gitcode.com/Stability-AI/generative-models.git",
            "https://gitclone.com/github.com/Stability-AI/generative-models.git"
        )
    },
    @{
        Name = "k-diffusion"
        Mirrors = @("https://github.com/crowsonkb/k-diffusion.git")
    },
    @{
        Name = "BLIP"
        Mirrors = @("https://github.com/salesforce/BLIP.git")
    },
    @{
        Name = "stable-diffusion-webui-assets"
        Mirrors = @("https://github.com/AUTOMATIC1111/stable-diffusion-webui-assets.git")
    }
)

foreach ($repo in $repos) {
    $repoDir = "$WebuiDir\repositories\$($repo.Name)"
    if (Test-Path "$repoDir\.git") {
        # Repo exists - point remote to mirror so future fetches don't fail
        $currentRemote = git -C $repoDir remote get-url origin 2>&1
        if ("$currentRemote" -match "github\.com/Stability-AI") {
            $newUrl = $repo.Mirrors[0]
            git -C $repoDir remote set-url origin $newUrl 2>&1 | Out-Null
            Write-Host "  $($repo.Name): remote switched to mirror"
        } else {
            Write-Host "  $($repo.Name): OK"
        }
    } else {
        Write-Host "  $($repo.Name): cloning..."
        $cloned = $false
        foreach ($mirror in $repo.Mirrors) {
            git clone --depth 1 $mirror $repoDir 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  $($repo.Name): OK (from $mirror)"
                $cloned = $true
                break
            } else {
                if (Test-Path $repoDir) { Remove-Item $repoDir -Recurse -Force 2>$null }
            }
        }
        if (-not $cloned) {
            Write-Host "  WARNING: Could not clone $($repo.Name) from any mirror" -ForegroundColor Yellow
        }
    }
}

# ── 6. Write definitive webui-user.bat ──
Write-Host "== [6/6] Write launch config ==" -ForegroundColor Cyan

$batContent = @"
@echo off
set PYTHON=$py310
set GIT=
set VENV_DIR=
set COMMANDLINE_ARGS=--api --medvram-sdxl --no-half-vae --xformers --skip-torch-cuda-test --skip-git
call webui.bat
"@

Set-Content "$WebuiDir\webui-user.bat" $batContent -Encoding ASCII
Write-Host "  webui-user.bat written"
Write-Host "  Flags: --api --medvram-sdxl --no-half-vae --xformers --skip-torch-cuda-test --skip-git"

# ── Done ──
Write-Host ""
Write-Host "===== Repair complete =====" -ForegroundColor Green
Write-Host "Now start WebUI:" -ForegroundColor Green
Write-Host "  cd $WebuiDir" -ForegroundColor Yellow
Write-Host "  .\webui-user.bat" -ForegroundColor Yellow
Write-Host "Target: see 'Running on local URL: http://127.0.0.1:7860'" -ForegroundColor Green
