@echo off
chcp 65001 >nul
:: 注册 Windows 任务计划：开机自动启动 GPU Worker（无需登录）
:: 以管理员身份运行此脚本

set REPO_DIR=C:\maomao-cooking
set TASK_NAME=MaomaoGPUWorker

schtasks /create /tn "%TASK_NAME%" /tr "\"%REPO_DIR%\worker\gpu\setup\start-gpu-worker.bat\"" /sc onstart /ru "%USERNAME%" /rl highest /f

if %errorlevel% equ 0 (
    echo [OK] 任务 "%TASK_NAME%" 已创建，开机将自动启动 GPU Worker
    echo     手动启动: schtasks /run /tn "%TASK_NAME%"
    echo     手动停止: schtasks /end /tn "%TASK_NAME%"
    echo     删除任务: schtasks /delete /tn "%TASK_NAME%" /f
) else (
    echo [ERROR] 创建失败，请以管理员身份运行此脚本
)
pause
