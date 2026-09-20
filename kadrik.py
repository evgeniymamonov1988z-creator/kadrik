"""
Kadrik / Кадрик — видео → кадры (фото).
Маленький квадрат с чёрным квадратом в центре: перетаскиваешь видео → программа режет его на кадры.
Язык: на российской Windows — по-русски, на остальных — по-английски.
Зависимости: tkinter (встроен), ffmpeg (системный), tkinterdnd2 (опционально для drag-and-drop).
"""

import os
import sys
import locale
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog
from pathlib import Path

# Пытаемся подключить drag-and-drop
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False

# Модуль авто-обновления (взят из mamonov-screen-recorder)
try:
    from updater import Updater
    HAS_UPDATER = True
except ImportError:
    HAS_UPDATER = False


def detect_lang():
    """Русский язык на российской Windows, иначе английский."""
    # Windows: язык интерфейса системы
    try:
        import ctypes
        lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        # Нижние 10 бит — основной язык; 0x19 = русский
        return "ru" if (lang_id & 0x3FF) == 0x19 else "en"
    except Exception:
        pass
    # Запасной вариант — локаль/переменные окружения
    try:
        loc = (locale.getdefaultlocale()[0] or "").lower()
    except Exception:
        loc = ""
    env = (os.environ.get("LANG", "") + os.environ.get("LC_ALL", "")).lower()
    if loc.startswith("ru") or env.startswith("ru"):
        return "ru"
    return "en"


LANG = detect_lang()

# Строки интерфейса (везде с большой буквы)
STRINGS = {
    "ru": {
        "app":        "Кадрик",
        "drop":       "Перетащи\nВидео",
        "update":     "Обновить",
        "wait":       "Жду видео…",
        "cutting":    "Нарезаю кадры…",
        "done":       "Готово: {n} кадров",
        "err_ffmpeg": "Ошибка ffmpeg",
        "err":        "Ошибка: {e}",
        "no_updater": "Модуль обновления не найден",
        "checking":   "Проверяю обновления…",
        "upd_err":    "Ошибка обновления: {e}",
        "pick_title": "Выбери видео",
        "filetype":   "Видео",
        "allfiles":   "Все файлы",
        # Ответы модуля обновления
        "Updated!":               "Обновлено!",
        "Already up to date":     "Уже актуально",
        "Connected!":             "Подключено!",
        "Connected and updated!": "Подключено и обновлено!",
    },
    "en": {
        "app":        "Kadrik",
        "drop":       "Drop\nVideo",
        "update":     "Update",
        "wait":       "Waiting For Video…",
        "cutting":    "Extracting Frames…",
        "done":       "Done: {n} Frames",
        "err_ffmpeg": "Ffmpeg Error",
        "err":        "Error: {e}",
        "no_updater": "Updater Module Not Found",
        "checking":   "Checking For Updates…",
        "upd_err":    "Update Error: {e}",
        "pick_title": "Choose Video",
        "filetype":   "Video",
        "allfiles":   "All Files",
        "Updated!":               "Updated!",
        "Already up to date":     "Already Up To Date",
        "Connected!":             "Connected!",
        "Connected and updated!": "Connected And Updated!",
    },
}


def T(key, **kw):
    s = STRINGS[LANG].get(key, key)
    return s.format(**kw) if kw else s


# Куда складываем кадры: папка Mamonov в домашнем каталоге, внутри — подпапка kadrik.
# Если их нет — создаются автоматически при добавлении видео.
BASE_DIR = Path.home() / "Mamonov" / "kadrik"

# Репозиторий для авто-обновления (SourceCraft, HTTPS — чтение без ключей/паролей)
REPO_URL = "https://git.sourcecraft.dev/evgeniymamonov1988/kadrik.git"
REPO_BRANCH = "main"

# Настройки по умолчанию (UI убран, берём как есть)
CFG = {
    "fps": 1,          # кадров в секунду (1 = 1 фото каждую секунду)
    "format": "png",   # png / jpg
    "quality": 95,     # качество jpg (1-100), для png не используется
}


def extract_frames(video_path, output_dir, cfg, log_fn=None):
    """Нарезает видео на кадры через ffmpeg."""
    fps = cfg["fps"]
    fmt = cfg["format"]
    quality = cfg["quality"]

    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(video_path)

    # Кадры складываем в Mamonov/kadrik/<имя_видео>_frames.
    if not output_dir:
        output_dir = BASE_DIR / f"{video_path.stem}_frames"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    ext = fmt if fmt in ("png", "jpg", "jpeg") else "png"
    pattern = output_dir / f"frame_%04d.{ext}"

    cmd = ["ffmpeg", "-i", str(video_path), "-vf", f"fps={fps}"]
    if ext in ("jpg", "jpeg"):
        cmd += ["-q:v", str(max(1, min(31, int(31 - quality * 30 / 100))))]
    else:
        cmd += ["-compression_level", "5"]
    cmd += [str(pattern), "-y"]

    if log_fn:
        log_fn(T("cutting"))

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        if log_fn:
            log_fn(T("err_ffmpeg"))
        raise RuntimeError(result.stderr[:300])

    files = sorted(output_dir.glob(f"*.{ext}"))
    if log_fn:
        log_fn(T("done", n=len(files)))
    return output_dir


class App:
    BG      = "#2b2b2b"
    FG      = "#d4d4d4"
    ACCENT  = "#61afef"

    def __init__(self):
        self.cfg = dict(CFG)

        self.root = TkinterDnD.Tk() if HAS_DND else tk.Tk()
        self.root.title(T("app"))
        self.root.geometry("130x150")
        self.root.configure(bg=self.BG)
        self.root.resizable(False, False)

        # Всегда поверх всех окон
        self.root.attributes("-topmost", True)
        # Сворачивается только по кнопке «_» (штатное поведение окна)

        self._build_ui()

        if HAS_DND:
            self.drop_area.drop_target_register(DND_FILES)
            self.drop_area.dnd_bind("<<Drop>>", self._on_drop)

        self.root.mainloop()

    def _build_ui(self):
        tk.Label(
            self.root, text=T("app"),
            bg=self.BG, fg=self.ACCENT, font=("Helvetica", 9, "bold")
        ).pack(pady=(5, 3))

        # Чёрный квадрат в центре — сюда перетаскивается видео
        self.drop_area = tk.Label(
            self.root,
            text=T("drop"),
            bg="#000000", fg="#777777",
            font=("Helvetica", 7),
            width=7, height=3,
        )
        self.drop_area.pack()
        self.drop_area.bind("<Button-1>", lambda e: self._pick_file())
        self.drop_area.bind("<Enter>", lambda e: self.drop_area.configure(bg="#111111"))
        self.drop_area.bind("<Leave>", lambda e: self.drop_area.configure(bg="#000000"))

        # Одна кнопка — Обновить (потом уберём)
        self.upd_btn = tk.Button(
            self.root, text=T("update"), bg=self.ACCENT, fg="white",
            font=("Helvetica", 7, "bold"), relief="flat",
            command=self._check_update
        )
        self.upd_btn.pack(pady=(5, 2))

        self.log_var = tk.StringVar(value=T("wait"))
        tk.Label(
            self.root, textvariable=self.log_var,
            bg=self.BG, fg="#888888", font=("Helvetica", 6),
            wraplength=118, justify="center"
        ).pack(pady=(0, 4))

    def _on_drop(self, event):
        raw = event.data
        path = raw.strip("{}").strip()
        if " " in raw and not raw.startswith("{"):
            path = raw.split()[0]
        self._process(path)

    def _pick_file(self):
        f = filedialog.askopenfilename(
            title=T("pick_title"),
            filetypes=[
                (T("filetype"), "*.mp4 *.avi *.mkv *.mov *.webm *.flv *.wmv *.m4v *.ts"),
                (T("allfiles"), "*.*"),
            ]
        )
        if f:
            self._process(f)

    def _process(self, video_path):
        def task():
            try:
                extract_frames(video_path, None, self.cfg, log_fn=self._log)
            except Exception as exc:
                self._log(T("err", e=exc))
        threading.Thread(target=task, daemon=True).start()

    def _log(self, msg):
        self.root.after(0, lambda: self.log_var.set(msg))

    def _check_update(self):
        if not HAS_UPDATER:
            # Модуля обновления нет — ничего не пишем, остаётся «Жду видео»
            return
        self.upd_btn.config(state="disabled")
        self._log(T("checking"))

        def task():
            try:
                upd = Updater(repo_url=REPO_URL, branch=REPO_BRANCH)
                ok, msg = upd.update()
                # Переводим известные ответы модуля обновления
                self._log(("✅ " if ok else "❌ ") + T(msg))
                if ok and "up to date" not in msg.lower():
                    self.root.after(1200, upd.restart)
            except Exception as exc:
                self._log(T("upd_err", e=exc))
            finally:
                self.root.after(0, lambda: self.upd_btn.config(state="normal"))
        threading.Thread(target=task, daemon=True).start()


if __name__ == "__main__":
    App()
