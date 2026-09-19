@echo off
chcp 65001 >nul
title Token Meter 停止工具
cd /d "%~dp0"

echo 正在停止监听 8722 端口的 Token Meter 服务...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$conns = Get-NetTCPConnection -LocalPort 8722 -ErrorAction SilentlyContinue; if ($conns) { $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique; foreach ($p in $pids) { Stop-Process -Id $p -Force -ErrorAction SilentlyContinue; Write-Host \"[成功] 已停止进程 PID: $p\" } } else { Write-Host \"[提示] 未发现运行中的 Token Meter 服务。\" }"

echo.
echo 完成。
timeout /t 2 >nul
