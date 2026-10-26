@echo off
rem Builds dist\nohin_barcode\nohin_barcode.exe on Windows (Python 3.12 required).
setlocal
cd /d "%~dp0.."
if not exist .venv-win py -3.12 -m venv .venv-win || goto :error
.venv-win\Scripts\python -m pip install --quiet --upgrade pip || goto :error
.venv-win\Scripts\pip install --quiet -r requirements.txt pyinstaller==6.16.0 || goto :error
.venv-win\Scripts\pyinstaller --noconfirm --clean --onedir --noconsole --name nohin_barcode --add-data "js;js" --exclude-module numpy --exclude-module PIL nohin_barcode.py || goto :error
copy /y build\install.bat dist\install.bat >nul
echo.
echo Build OK: dist\nohin_barcode\nohin_barcode.exe
exit /b 0
:error
echo Build FAILED.
exit /b 1
