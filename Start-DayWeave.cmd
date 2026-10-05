@echo off
cd /d "%~dp0"
py -3 launch.py
if errorlevel 1 (
  echo Install Python 3.12 from python.org, then start DayWeave again.
  pause
)
