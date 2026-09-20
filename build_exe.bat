@echo off
chcp 65001 >nul
REM ==== Сборка Кадрика в .exe БЕЗ чёрного окна консоли ====
REM Просто запустите этот файл двойным щелчком.
REM Готовый Kadrik.exe появится в папке dist.

echo Готовлю сборку...
python -m pip install --upgrade pyinstaller pillow tkinterdnd2

echo Собираю Kadrik.exe (без консоли)...
python -m PyInstaller --noconfirm --onefile --noconsole --name Kadrik ^
  --collect-all tkinterdnd2 --collect-all PIL ^
  kadrik.py

echo.
echo Готово! Файл Kadrik.exe лежит в папке dist.
pause
