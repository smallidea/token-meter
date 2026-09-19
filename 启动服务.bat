@echo off
chcp 65001 >nul
title Token Meter - AI 编码智能体 Token 与开销监控看板
cd /d "%~dp0"

echo =========================================================
echo       Token Meter 增强版 (简体中文 / 多模型 / 全生态)
echo =========================================================
echo.
echo   Web 仪表盘:  http://127.0.0.1:8722
echo   部署路径:    %~dp0
echo   支持工具:    Claude Code / Codex / Cursor / OpenCode
echo                + Antigravity (Google / Codeium)
echo                + WorkBuddy (腾讯混元 / 深度适配)
echo                + Trae CN (字节跳动 / 豆包 / GLM)
echo.
echo   [使用提示]
echo   1. 保持本窗口打开（可最小化），服务即可在后台持续统计。
echo   2. 如需停止服务，直接关闭本窗口或双击 停止服务.bat 即可。
echo   3. 日后通过 git pull 升级官方代码时，汉化与自定义支持均不受影响。
echo =========================================================
echo.

:: 1. 检查并清理残留的 8722 端口占用
powershell -NoProfile -ExecutionPolicy Bypass -Command "$c=Get-NetTCPConnection -LocalPort 8722 -ErrorAction SilentlyContinue; if($c){ $p=$c|Select-Object -ExpandProperty OwningProcess -Unique; foreach($id in $p){ Stop-Process -Id $id -Force -ErrorAction SilentlyContinue } }" >nul 2>nul

:: 2. 确保中文页面存在
if not exist "%~dp0page_zh.html" (
    echo 正在生成简体中文页面...
    python -X utf8 "%~dp0custom\build_zh_page.py"
)

:: 3. 设置自定义中文前端页面环境变量
set TOKEN_METER_PAGE=%~dp0page_zh.html

:: 4. 启动后台就绪探测器：等待后端 HTTP 服务完全就绪后，再弹出浏览器（彻底杜绝打开时报错或断连）
start /b powershell -NoProfile -ExecutionPolicy Bypass -Command "$u='http://127.0.0.1:8722/health'; for($i=0;$i -lt 40;$i++){ try { $res=Invoke-WebRequest -Uri $u -TimeoutSec 1 -UseBasicParsing -ErrorAction Stop; if($res.StatusCode -eq 200){ Start-Process 'http://127.0.0.1:8722'; break } } catch { Start-Sleep -Milliseconds 400 } }"

:: 5. 启动增强版主服务
echo 正在启动 Token Meter 服务并初始化索引...
python -X utf8 meter_custom.py

echo.
echo 服务已退出。
pause
