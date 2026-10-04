@echo off
setlocal
set ROOT=%~dp0..
cd /d "%ROOT%"

echo === BiliRag 一键启动 ===

echo [1/3] 安装后端依赖...
cd backend
if not exist ".venv\Scripts\python.exe" (
    echo   创建虚拟环境...
    python -m venv .venv
)
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt
cd "%ROOT%"

echo [2/3] 构建前端...
cd frontend
if not exist "node_modules" (
    call npm install
)
call npm run build
cd "%ROOT%"

echo [3/3] 启动后端并打开浏览器...
start "" http://127.0.0.1:8000
cd backend
".venv\Scripts\python.exe" run.py

endlocal
