@echo off
chcp 65001 >nul
title Token Meter - 同步数据到 Apache Doris
echo ===============================================================================
echo                Token Meter - AI Token 度量数据同步到 Doris
echo ===============================================================================
echo.

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

set "PYTHON_CMD="
if exist "%SCRIPT_DIR%PYTHON_EXECUTABLE" (
    set /p PYTHON_CMD=<"%SCRIPT_DIR%PYTHON_EXECUTABLE"
)
if "%PYTHON_CMD%"=="" (
    where python >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_CMD=python"
    ) else (
        where py >nul 2>nul
        if not errorlevel 1 (
            set "PYTHON_CMD=py"
        )
    )
)

if "%PYTHON_CMD%"=="" (
    echo [错误] 未检测到 Python 环境，请先安装 Python 3.10+。
    pause
    exit /b 1
)

echo [提示] 正在执行本地数据抽取与离线导出...
"%PYTHON_CMD%" custom/doris_sync.py --dry-run

echo.
echo ===============================================================================
echo  离线数据已成功导出至 custom/exports/ 目录。
echo.
echo  如需推送到线上 Doris 集群，请按如下格式运行:
echo    python custom/doris_sync.py --push --host ^<DORIS_FE_IP^> --port 8030 --db ods_dev --user root --password ^<密码^>
echo ===============================================================================
echo.
pause
