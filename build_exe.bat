@echo off
chcp 65001 >nul
REM ==== Sborka Kadrik.exe BEZ chyornogo okna ====
REM Prosto zapustite etot fayl dvoynym schelchkom.
echo Gotovlyu sborku...
python -m pip install --upgrade pyinstaller pillow tkinterdnd2
echo Sobirayu Kadrik.exe...
python -m PyInstaller --noconfirm --onefile --noconsole --name Kadrik --icon icon.ico --collect-all tkinterdnd2 --collect-all PIL kadrik.py
echo.
REM ==== Pereimenovyvaem v "Demo Kadrik.exe" (kirillica iz Unicode-kodov) ====
powershell -NoProfile -Command "$c=[char[]](0x041A,0x0430,0x0434,0x0440,0x0438,0x043A); $n='Demo '+(-join $c)+'.exe'; if (Test-Path 'dist\Kadrik.exe'){ Rename-Item -LiteralPath 'dist\Kadrik.exe' -NewName $n -Force; Write-Host ('[OK] dist\'+$n) }"
echo.
echo Gotovo! Fayl 'Demo Kadrik.exe' lezhit v papke dist.
pause
