@echo off
chcp 65001 >nul
title 猫猫炒菜 GPU Worker

:: ===== 配置 =====
:: 修改为你的实际路径
set REPO_DIR=E:\maomao-cooking
set PYTHON=python

:: Azure 连接串（从 .env-maomao 读取，或直接写在这里）
if exist "%USERPROFILE%\.env-maomao" (
    for /f "usebackq tokens=1,* delims==" %%a in ("%USERPROFILE%\.env-maomao") do set %%a=%%b
)

:: 默认 dev 环境
if not defined MAOMAO_ENV set MAOMAO_ENV=dev

:: ===== 启动 =====
cd /d %REPO_DIR%
echo [GPU Worker] 环境=%MAOMAO_ENV%
echo [GPU Worker] 启动中...

:loop
%PYTHON% -m worker.gpu.worker_loop
echo [GPU Worker] 进程退出，10秒后重启...
timeout /t 10 /nobreak >nul
goto loop
