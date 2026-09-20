@echo off
chcp 65001 >nul
REM ==== Sborka Kadrik.exe BEZ chyornogo okna ====
REM Prosto zapustite etot fayl dvoynym schelchkom.
echo Gotovlyu sborku...
python -m pip install --upgrade pyinstaller pillow tkinterdnd2
echo Sobirayu Kadrik.exe...
python -m PyInstaller --noconfirm --onefile --noconsole --name Kadrik --icon icon.ico --collect-all tkinterdnd2 --collect-all PIL kadrik.py
echo.
echo Gotovo! Fayl Kadrik.exe lezhit v papke dist.
pause
