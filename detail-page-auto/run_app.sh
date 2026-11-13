#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "먼저 Python 3.12 가상환경과 의존성을 설치하세요. README의 화면으로 사용하기 절을 확인하세요."
  exit 1
fi
exec .venv/bin/python -m streamlit run app/main.py --server.address 127.0.0.1 --browser.gatherUsageStats false
