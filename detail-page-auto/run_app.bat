@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Python 3.12 가상환경과 의존성을 먼저 설치하세요. README를 확인하세요.
  exit /b 1
)
".venv\Scripts\python.exe" -m streamlit run app/main.py --server.address 127.0.0.1 --browser.gatherUsageStats false
