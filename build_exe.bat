@echo off
chcp 65001 >nul
rem Builds MewTree.exe: one file, no Python needed to run it.
cd /d "%~dp0"
set "PY="
py -3 -c "import sys" >nul 2>nul && set "PY=py -3"
if not defined PY python -c "import sys" >nul 2>nul && set "PY=python"
if not defined PY goto :nopython
echo [1/2] Installing PyInstaller...
%PY% -m pip install --user --upgrade pyinstaller
if errorlevel 1 goto :fail
echo [2/2] Building MewTree.exe, this takes a minute or two...
%PY% -m PyInstaller --noconfirm --onefile --console --name MewTree --add-data "%~dp0src\template.html;." --paths "%~dp0src" --hidden-import mewsave --hidden-import locate --hidden-import catface --hidden-import mewfont --distpath "%~dp0." --workpath "%~dp0build" --specpath "%~dp0build" "%~dp0src\build_tree.py"
if errorlevel 1 goto :fail
rmdir /s /q "%~dp0build" >nul 2>nul
echo.
echo Done: MewTree.exe is next to this file. Copy it anywhere and double-click it,
echo or drop a .sav file onto it. It writes mewtree.html and mewtree.json next to itself.
pause
exit /b 0

:fail
echo.
echo The build failed. The text above says why.
pause
exit /b 1

:nopython
echo.
echo Python was not found. Install Python 3.10 or newer: https://www.python.org/downloads/
echo Tick "Add python.exe to PATH" in the installer, then run this file again.
pause
exit /b 1
