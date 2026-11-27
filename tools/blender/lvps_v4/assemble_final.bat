@echo off
setlocal
if "%LVPS_ROOT%"=="" (
  for %%I in ("%~dp0..\..\..\..") do set "LVPS_ROOT=%%~fI"
)
if "%PYTHON%"=="" set PYTHON=py
"%PYTHON%" -3 "%~dp0assemble_final.py" %*
if errorlevel 1 "%PYTHON%" "%~dp0assemble_final.py" %*
endlocal
