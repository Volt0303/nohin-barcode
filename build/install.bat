@echo off
rem Copies the tool from this shared folder to C:\YukiSoft\nohin_barcode on this PC.
rem Run once on each issuing PC, and again after an update.
robocopy "%~dp0nohin_barcode" "C:\YukiSoft\nohin_barcode" /MIR /NFL /NDL /NJH /NJS /NP
if %ERRORLEVEL% GEQ 8 (echo Install FAILED. & pause & exit /b 1)
echo Installed: C:\YukiSoft\nohin_barcode\nohin_barcode.exe
pause
