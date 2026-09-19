@echo off
chcp 65001 >nul
title Token Meter 桌面端
echo ========================================
echo   Token Meter 桌面端启动中...
echo ========================================

cd /d "%~dp0"

:: 检测 Python 可执行文件
if exist PYTHON_EXECUTABLE (
    set /p PYTHON=<PYTHON_EXECUTABLE
) else (
    set PYTHON=python
)

:: 启动桌面端
%PYTHON% desktop\main.py

if errorlevel 1 (
    echo.
    echo [错误] 启动失败，请检查 PySide6 是否已安装：
    echo   pip install PySide6
    echo.
    pause
)
