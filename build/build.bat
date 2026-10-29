@echo off
rem Builds dist\nohin_barcode\nohin_barcode.exe on Windows (Python 3.12 required).
setlocal
cd /d "%~dp0.."
if exist .venv-win goto :deps

rem Find Python 3.12: the py launcher, then the default per-user install, then PATH.
set "PY="
where py >nul 2>nul && set "PY=py -3.12"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY="%LOCALAPPDATA%\Programs\Python\Python312\python.exe""
if not defined PY set "PY=python"
%PY% -m venv .venv-win || goto :error

:deps
.venv-win\Scripts\python -m pip install --quiet --upgrade pip || goto :error
.venv-win\Scripts\python -m pip install --quiet -r requirements.txt pyinstaller==6.16.0 || goto :error
.venv-win\Scripts\python -m PyInstaller --noconfirm --clean --onedir --noconsole --name nohin_barcode --add-data "js;js" --exclude-module numpy --exclude-module PIL nohin_barcode.py || goto :error
copy /y build\install.bat dist\install.bat >nul
echo.
echo Build OK: dist\nohin_barcode\nohin_barcode.exe
exit /b 0
:error
echo Build FAILED.
exit /b 1
