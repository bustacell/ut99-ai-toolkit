@echo off
setlocal
REM LVPS Vol. 4 1080p finals. Default device is CPU; pass --device GPU for Cycles GPU.
if "%LVPS_ROOT%"=="" (
  REM this bat lives in render\lvps\v4\tools ; kit root is 4 levels up
  for %%I in ("%~dp0..\..\..\..") do set "LVPS_ROOT=%%~fI"
)
if "%PYTHON%"=="" set PYTHON=py
"%PYTHON%" -3 "%~dp0render_finals.py" %*
if errorlevel 1 "%PYTHON%" "%~dp0render_finals.py" %*
endlocal
