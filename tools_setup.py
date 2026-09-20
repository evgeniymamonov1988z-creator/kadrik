"""
tools_setup.py — авто-загрузка всего необходимого в одну папку bin/.

Всё (движок ffmpeg/ffprobe и python-библиотеки) складывается в
    <домашняя>/Mamonov/kadrik/bin
Перед каждым запуском проверяем: если чего-то нет — скачиваем заново.
"""

import os
import sys
import zipfile
import shutil
import tempfile
import subprocess
import urllib.request
from pathlib import Path

# Единая папка для всех библиотек и движка — на Рабочем столе: Mamonov/kadrik/bin
def _desktop_dir():
    d = Path.home() / "Desktop"
    if d.exists():
        return d
    ru = Path.home() / "Рабочий стол"
    if ru.exists():
        return ru
    return d

BIN_DIR = _desktop_dir() / "Mamonov" / "kadrik" / "bin"

# --- Язык сообщений (русский / английский) ---
def _detect_lang():
    try:
        import ctypes
        lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        return "ru" if (lang_id & 0x3FF) == 0x19 else "en"
    except Exception:
        pass
    try:
        import locale
        loc = (locale.getdefaultlocale()[0] or "").lower()
    except Exception:
        loc = ""
    env = (os.environ.get("LANG", "") + os.environ.get("LC_ALL", "")).lower()
    return "ru" if (loc.startswith("ru") or env.startswith("ru")) else "en"

LANG = _detect_lang()

_MSG = {
    "ru": {
        "dl":      "Скачиваю движок",
        "mb":      "МБ",
        "pillow":  "Готовлю оценку чёткости…",
        "dnd":     "Готовлю перетаскивание…",
        "install": "Ставлю {pip}…",
    },
    "en": {
        "dl":      "Downloading engine",
        "mb":      "MB",
        "pillow":  "Preparing sharpness check…",
        "dnd":     "Preparing drag-and-drop…",
        "install": "Installing {pip}…",
    },
}


def set_lang(lang):
    """Задать язык сообщений (вызывает основная программа)."""
    global LANG
    if lang in _MSG:
        LANG = lang


def _m(key, **kw):
    s = _MSG.get(LANG, _MSG["en"]).get(key, key)
    return s.format(**kw) if kw else s

# Готовая статичная сборка ffmpeg для Windows 64-bit (ffmpeg.exe + ffprobe.exe)
FFMPEG_WIN_URL = (
    "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
    "ffmpeg-master-latest-win64-gpl.zip"
)


def bin_dir():
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    return BIN_DIR


def add_to_path():
    """Добавляет bin/ в пути Python, чтобы оттуда грузились библиотеки."""
    p = str(BIN_DIR)
    if p not in sys.path:
        sys.path.insert(0, p)


def _exe(name):
    return name + ".exe" if os.name == "nt" else name


def find_tools():
    """(ffmpeg, ffprobe) если есть (сначала в bin/, потом в системе), иначе (None, None)."""
    lf = BIN_DIR / _exe("ffmpeg")
    lp = BIN_DIR / _exe("ffprobe")
    if lf.exists() and lp.exists():
        return str(lf), str(lp)
    sysf = shutil.which("ffmpeg")
    sysp = shutil.which("ffprobe")
    if sysf and sysp:
        return sysf, sysp
    return None, None


def _download(url, dst, log_fn=None, label=""):
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
                        log_fn(f"{label} {pct}% ({total/1048576:.0f} {_m('mb')})")


def ensure_ffmpeg(log_fn=None):
    """Гарантирует ffmpeg/ffprobe. Нет — скачивает в bin/ (только Windows). (ffmpeg, ffprobe) | (None, None)."""
    ffm, ffp = find_tools()
    if ffm and ffp:
        return ffm, ffp
    if os.name != "nt":
        return None, None

    bin_dir()
    tmpdir = Path(tempfile.mkdtemp(prefix="kadrik_ff_"))
    zip_path = tmpdir / "ffmpeg.zip"
    try:
        if log_fn:
            log_fn(_m("dl") + "…")
        _download(FFMPEG_WIN_URL, zip_path, log_fn=log_fn, label=_m("dl"))
        with zipfile.ZipFile(zip_path) as z:
            for member in z.namelist():
                base = os.path.basename(member)
                if base.lower() in ("ffmpeg.exe", "ffprobe.exe"):
                    with z.open(member) as src, open(BIN_DIR / base, "wb") as out:
                        shutil.copyfileobj(src, out)
        return find_tools()
    except Exception:
        return None, None
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def ensure_pip_package(import_name, pip_name, log_fn=None, label=None):
    """Проверяет python-библиотеку; нет — ставит её в bin/ через pip. True/False."""
    import importlib
    add_to_path()
    try:
        __import__(import_name)
        return True
    except Exception:
        pass
    try:
        if log_fn:
            log_fn(label or _m("install", pip=pip_name))
        bin_dir()
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", "--upgrade",
             "--target", str(BIN_DIR), pip_name],
            timeout=600)
        add_to_path()
        # Важно: после появления новых файлов обновляем кэш поиска модулей,
        # иначе свежеустановленная библиотека не найдётся в этом же запуске.
        importlib.invalidate_caches()
        __import__(import_name)
        return True
    except Exception:
        return False


def ensure_pillow(log_fn=None):
    return ensure_pip_package("PIL", "Pillow", log_fn=log_fn,
                              label=_m("pillow"))


def ensure_dnd(log_fn=None):
    return ensure_pip_package("tkinterdnd2", "tkinterdnd2", log_fn=log_fn,
                              label=_m("dnd"))
