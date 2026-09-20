"""
tools_setup.py — авто-загрузка необходимых инструментов при первом запуске.

Главное — ffmpeg и ffprobe (движок нарезки видео). Если их нет
ни в папке программы, ни в системе — скачиваем готовую сборку для Windows
в подпапку bin/ рядом с программой.

Всё скачивается только один раз: при следующих запусках берём из bin/.
"""

import os
import sys
import zipfile
import shutil
import tempfile
import urllib.request
from pathlib import Path

# Готовая статичная сборка ffmpeg для Windows 64-bit (включает ffmpeg.exe и ffprobe.exe)
FFMPEG_WIN_URL = (
    "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
    "ffmpeg-master-latest-win64-gpl.zip"
)


def app_dir():
    """Папка с программой (работает и для .exe, и для .py)."""
    if getattr(sys, "frozen", False):
        return Path(os.path.dirname(os.path.abspath(sys.executable)))
    return Path(os.path.dirname(os.path.abspath(__file__)))


def _exe(name):
    return name + ".exe" if os.name == "nt" else name


def _local_bin():
    return app_dir() / "bin"


def find_tools():
    """Возвращает (ffmpeg_path, ffprobe_path) если уже есть, иначе (None, None).
    Сначала смотрим в свою папку bin/, потом в системе."""
    binv = _local_bin()
    lf = binv / _exe("ffmpeg")
    lp = binv / _exe("ffprobe")
    if lf.exists() and lp.exists():
        return str(lf), str(lp)
    sysf = shutil.which("ffmpeg")
    sysp = shutil.which("ffprobe")
    if sysf and sysp:
        return sysf, sysp
    return None, None


def _download(url, dst, log_fn=None, label=""):
    """Скачивание файла с показом прогресса."""
    req = urllib.request.Request(url, headers={"User-Agent": "Kadrik"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        total = int(resp.headers.get("Content-Length", 0) or 0)
        got = 0
        last_pct = -1
        with open(dst, "wb") as f:
            while True:
                chunk = resp.read(262144)
                if not chunk:
                    break
                f.write(chunk)
                got += len(chunk)
                if log_fn and total:
                    pct = int(got * 100 / total)
                    if pct != last_pct and pct % 5 == 0:
                        last_pct = pct
                        mb = total / 1048576
                        log_fn(f"{label} {pct}% ({mb:.0f} МБ)")


def ensure_ffmpeg(log_fn=None):
    """Гарантирует наличие ffmpeg/ffprobe. Возвращает (ffmpeg, ffprobe) или (None, None).
    Если инструментов нет и это Windows — скачивает их в папку bin/."""
    ffm, ffp = find_tools()
    if ffm and ffp:
        return ffm, ffp

    # Скачивание поддерживаем только для Windows (готовые .exe)
    if os.name != "nt":
        return None, None

    binv = _local_bin()
    binv.mkdir(parents=True, exist_ok=True)
    tmpdir = Path(tempfile.mkdtemp(prefix="kadrik_ff_"))
    zip_path = tmpdir / "ffmpeg.zip"
    try:
        if log_fn:
            log_fn_start = log_fn
            log_fn_start("Скачиваю движок…")
        _download(FFMPEG_WIN_URL, zip_path, log_fn=log_fn, label="Скачиваю движок")

        # Распаковываем только ffmpeg.exe и ffprobe.exe
        with zipfile.ZipFile(zip_path) as z:
            for member in z.namelist():
                base = os.path.basename(member)
                if base.lower() in ("ffmpeg.exe", "ffprobe.exe"):
                    with z.open(member) as src, open(binv / base, "wb") as out:
                        shutil.copyfileobj(src, out)

        ffm, ffp = find_tools()
        return ffm, ffp
    except Exception:
        return None, None
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def ensure_pillow(log_fn=None):
    """Пробует подключить Pillow; если нет — тихо ставит через pip. Возвращает True/False."""
    try:
        import PIL  # noqa: F401
        return True
    except Exception:
        pass
    try:
        import subprocess
        if log_fn:
            log_fn("Готовлю оценку чёткости…")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", "Pillow"],
            timeout=300)
        import PIL  # noqa: F401
        return True
    except Exception:
        return False
