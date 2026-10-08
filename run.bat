@echo off
chcp 65001 >nul
rem Builds the tree from the newest save, opens it in the browser and rebuilds it after every save in the game.
rem Pick another account or save: run.bat --pick    Show what was found and where: run.bat --list
cd /d "%~dp0"
set "PY="
py -3 -c "import sys" >nul 2>nul && set "PY=py -3"
if not defined PY python -c "import sys" >nul 2>nul && set "PY=python"
if not defined PY goto :nopython
%PY% "%~dp0build_tree.py" --watch %*
pause
exit /b 0

:nopython
echo.
echo Python was not found. Install Python 3.10 or newer: https://www.python.org/downloads/
echo Tick "Add python.exe to PATH" in the installer, then run this file again.
echo Or just use MewTree.exe from the releases: it needs no Python.
echo.
echo Не нашёл Python. Поставь Python 3.10 или новее и отметь "Add python.exe to PATH",
echo либо возьми готовый MewTree.exe из релизов: ему Python не нужен.
pause
exit /b 1
