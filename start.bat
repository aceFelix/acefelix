@echo off
chcp 65001 >nul
REM ============================================
REM  AceFelix 知识图谱 一键启动脚本
REM  启动后端 (FastAPI :8800) + 前端 (Vite :5173)
REM ============================================

echo ============================================
echo   AceFelix 知识图谱启动中...
echo ============================================

REM ---- 1. 检查并启动后端 ----
set BACKEND_PORT=8800
netstat -ano | findstr ":%BACKEND_PORT%" | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
    echo [OK] 后端已在端口 %BACKEND_PORT% 运行
) else (
    echo [..] 启动后端 (http://127.0.0.1:%BACKEND_PORT%)...
    start "AceFelix-Backend" /min cmd /c "cd /d %~dp0backend && python api.py"
    timeout /t 3 /nobreak >nul
)

REM ---- 2. 检查并启动前端 ----
set FRONTEND_PORT=5173
netstat -ano | findstr ":%FRONTEND_PORT%" | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
    echo [OK] 前端已在端口 %FRONTEND_PORT% 运行
) else (
    echo [..] 启动前端 (http://localhost:%FRONTEND_PORT%)...
    start "AceFelix-Frontend" /min cmd /c "cd /d %~dp0frontend && set TMP=%~dp0frontend\.tmp && set TEMP=%~dp0frontend\.tmp && npx vite --host"
    timeout /t 5 /nobreak >nul
)

REM ---- 3. 打开浏览器 ----
echo ============================================
echo   启动完成！正在打开浏览器...
echo   前端: http://localhost:%FRONTEND_PORT%
echo   后端: http://127.0.0.1:%BACKEND_PORT%
echo ============================================
start "" "http://localhost:%FRONTEND_PORT%"
echo.
echo 提示: 关闭本窗口不影响服务运行。
echo       停止服务: 关闭标题为 AceFelix-Backend/AceFelix-Frontend 的窗口
pause
