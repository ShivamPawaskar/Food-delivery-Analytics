@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Create the project environment first: py -m venv .venv
  echo Then install dependencies: .venv\Scripts\python.exe -m pip install -r requirements.txt
  exit /b 1
)
if not exist "frontend\node_modules" (
  echo Installing React dashboard packages for the first run...
  call npm.cmd --prefix frontend install
  if errorlevel 1 exit /b 1
)
".venv\Scripts\python.exe" -c "import fastapi, uvicorn" >nul 2>&1
if errorlevel 1 (
  echo Install Python requirements first: .venv\Scripts\python.exe -m pip install -r requirements.txt
  exit /b 1
)
".venv\Scripts\python.exe" -m api.run_local
