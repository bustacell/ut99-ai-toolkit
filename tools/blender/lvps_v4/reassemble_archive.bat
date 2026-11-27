@echo off
setlocal
if "%PYTHON%"=="" set PYTHON=py
"%PYTHON%" -3 "%~dp0reassemble_archive.py" %*
if errorlevel 1 "%PYTHON%" "%~dp0reassemble_archive.py" %*
endlocal
