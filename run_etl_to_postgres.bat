@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Create the project environment and install requirements first. See README.md.
  exit /b 1
)
call ".venv\Scripts\activate.bat"
python -m database.setup --create-database
if errorlevel 1 exit /b %errorlevel%
python generate_dataset.py
if errorlevel 1 exit /b %errorlevel%
python -m etl.pipeline --load-to-database
if errorlevel 1 exit /b %errorlevel%
python -m database.check_data
