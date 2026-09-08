@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
REM ============================================
REM  aceFelix 知识图谱 一键启动脚本
REM  启动后端 (FastAPI :8800) + 前端 (Vite :5173)
REM  改进点（aceFelix）：
REM    1. 就绪探测替代固定 timeout：服务真正可响应后才开浏览器，
REM       避免 Vite 冷启动（依赖预构建 10~30s）期间打开报错页
REM    2. 启动输出落盘 logs/，派生窗口异常时可事后排查
REM    3. 自动创建 frontend\.tmp（Vite/esbuild 临时目录，缺失会冷启动失败）
REM    4. set "TMP=..." 引号写法，避免值带尾随空格
REM ============================================

echo ============================================
echo   aceFelix 知识图谱启动中...
echo ============================================

set "LOGDIR=%~dp0logs"
if not exist "%LOGDIR%" md "%LOGDIR%"
if not exist "%~dp0frontend\.tmp" md "%~dp0frontend\.tmp"

REM ---- 1. 检查并启动后端 ----
set BACKEND_PORT=8800
netstat -ano | findstr ":%BACKEND_PORT%" | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
    echo [OK] 后端已在端口 %BACKEND_PORT% 运行
) else (
    echo [..] 启动后端 (http://127.0.0.1:%BACKEND_PORT%)...
    start "AceFelix-Backend" /min cmd /c "cd /d %~dp0backend && python api.py >> "%LOGDIR%\backend.log" 2>&1"
    call :wait_ready http://127.0.0.1:%BACKEND_PORT%/api/stats 30 后端
)

REM ---- 2. 检查并启动前端 ----
set FRONTEND_PORT=5173
netstat -ano | findstr ":%FRONTEND_PORT%" | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
    echo [OK] 前端已在端口 %FRONTEND_PORT% 运行
) else (
    echo [..] 启动前端 (http://localhost:%FRONTEND_PORT%，冷启动可能需数十秒)...
    start "AceFelix-Frontend" /min cmd /c "cd /d %~dp0frontend && set "TMP=%~dp0frontend\.tmp" && set "TEMP=%~dp0frontend\.tmp" && npx vite --host >> "%LOGDIR%\frontend.log" 2>&1"
    call :wait_ready http://localhost:%FRONTEND_PORT%/ 60 前端
)

REM ---- 3. 打开浏览器（前端就绪后才开，避免报错页） ----
echo ============================================
echo   启动完成！正在打开浏览器...
echo   前端: http://localhost:%FRONTEND_PORT%
echo   后端: http://127.0.0.1:%BACKEND_PORT%
echo ============================================
start "" "http://localhost:%FRONTEND_PORT%"
echo.
echo 提示: 关闭本窗口不影响服务运行。
echo       停止服务: 关闭标题为 aceFelix-Backend/aceFelix-Frontend 的窗口
echo       启动日志: %LOGDIR%
pause
exit /b 0

REM ---- 就绪探测子程序： %1=探测URL %2=超时秒数 %3=显示名 ----
REM 每秒 HTTP 探测一次，成功立即返回；超时则提示查日志
:wait_ready
set /a _waited=0
:wait_ready_loop
REM ping 自身 1 秒作为 sleep（timeout 命令在无控制台/重定向环境会报错）
ping -n 2 127.0.0.1 >nul
set /a _waited+=1
powershell -NoProfile -Command "try{(Invoke-WebRequest -Uri '%~1' -UseBasicParsing -TimeoutSec 1)|Out-Null;exit 0}catch{exit 1}" >nul 2>&1
if %errorlevel%==0 (
    echo [OK] %~3已就绪（耗时 %_waited% 秒）
    exit /b 0
)
if %_waited% GEQ %~2 (
    echo [!!] %~3 %~2 秒内未就绪，请查看 %LOGDIR% 下的日志排查
    exit /b 1
)
goto wait_ready_loop
