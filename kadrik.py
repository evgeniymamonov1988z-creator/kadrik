"""
Кадрик — видео → кадры (фото)
Маленькая панель: перетаскиваешь видео → программа режет его на кадры.
Зависимости: tkinter (встроен), ffmpeg (системный), tkinterdnd2 (опционально для drag & drop).
"""

import os
import sys
import json
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
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


# ── Куда складываем кадры ────────────────────────────────────────────────
# Папка Mamonov в домашнем каталоге пользователя, внутри — подпапка kadrik.
# Если их нет — создаются автоматически при добавлении видео.
BASE_DIR = Path.home() / "Mamonov" / "kadrik"

# Репозиторий для авто-обновления (SourceCraft)
REPO_URL = "ssh://git@ssh.sourcecraft.dev/evgeniymamonov1988/kadrik.git"
REPO_BRANCH = "main"


# ── Настройки по умолчанию ──────────────────────────────────────────────
CONFIG_PATH = Path(__file__).parent / "settings.json"
DEFAULTS = {
    "fps": 1,          # кадров в секунду (1 = 1 фото каждую секунду)
    "format": "png",   # png / jpg
    "quality": 95,     # качество jpg (1-100), для png не используется
}


def load_config():
    if CONFIG_PATH.exists():
        try:
            return {**DEFAULTS, **json.loads(CONFIG_PATH.read_text())}
        except Exception:
            pass
    return dict(DEFAULTS)


def save_config(cfg):
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))


# ── Логика нарезки ──────────────────────────────────────────────────────
def extract_frames(video_path, output_dir, cfg, log_fn=None):
    """Нарезает видео на кадры через ffmpeg."""
    fps = cfg["fps"]
    fmt = cfg["format"]
    quality = cfg["quality"]

    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(video_path)

    # Кадры складываем в Mamonov/kadrik/<имя_видео>_frames.
    # Папки Mamonov и kadrik создаются автоматически, если их ещё нет.
    if not output_dir:
        output_dir = BASE_DIR / f"{video_path.stem}_frames"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Шаблон имени: frame_0001.png / frame_0001.jpg
    ext = fmt if fmt in ("png", "jpg", "jpeg") else "png"
    pattern = output_dir / f"frame_%04d.{ext}"

    # Собираем команду ffmpeg
    cmd = [
        "ffmpeg", "-i", str(video_path),
        "-vf", f"fps={fps}",
    ]
    if ext in ("jpg", "jpeg"):
        cmd += ["-q:v", str(max(1, min(31, int(31 - quality * 30 / 100))))]
    else:
        cmd += ["-compression_level", "5"]
    cmd += [str(pattern), "-y"]

    if log_fn:
        log_fn(f"⏳ Нарезаю: {video_path.name} → {fps} fps, {ext}…")

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        if log_fn:
            log_fn(f"❌ Ошибка ffmpeg:\n{result.stderr[:500]}")
        raise RuntimeError(result.stderr[:300])

    files = sorted(output_dir.glob(f"*.{ext}"))
    if log_fn:
        log_fn(f"✅ Готово! {len(files)} кадров → {output_dir}")
    return output_dir


# ── GUI ─────────────────────────────────────────────────────────────────
class App:
    BG       = "#2b2b2b"
    BG_PANEL = "#3c3f41"
    FG       = "#d4d4d4"
    ACCENT   = "#4e9a6d"
    ACCENT2  = "#61afef"

    def __init__(self):
        self.cfg = load_config()

        # Окно
        if HAS_DND:
            self.root = TkinterDnD.Tk()
        else:
            self.root = tk.Tk()

        self.root.title("🎬 Кадрик")
        self.root.geometry("380x340")
        self.root.configure(bg=self.BG)
        self.root.resizable(False, False)

        # Всегда поверх всех окон
        self.root.attributes("-topmost", True)
        # Не сворачивается: если окно свернули — тут же разворачиваем обратно
        self.root.bind("<Unmap>", self._prevent_minimize)

        self._build_ui()

        # Drag & drop
        if HAS_DND:
            self.drop_area.drop_target_register(DND_FILES)
            self.drop_area.dnd_bind("<<Drop>>", self._on_drop)

        self.root.mainloop()

    # ── Интерфейс ────────────────────────────────────────────────────────
    def _build_ui(self):
        # Заголовок
        tk.Label(
            self.root, text="Кадрик · перетащи видео сюда",
            bg=self.BG, fg=self.ACCENT2, font=("Helvetica", 13, "bold")
        ).pack(pady=(12, 4))

        # Зона перетаскивания
        self.drop_area = tk.Label(
            self.root,
            text="📂  drag & drop\nили кликни для выбора",
            bg=self.BG_PANEL, fg=self.FG,
            font=("Helvetica", 11),
            relief="groove", bd=2,
            width=30, height=4,
        )
        self.drop_area.pack(padx=20, pady=6)
        self.drop_area.bind("<Button-1>", lambda e: self._pick_file())
        self.drop_area.bind("<Enter>", lambda e: self.drop_area.configure(bg="#4a4d50"))
        self.drop_area.bind("<Leave>", lambda e: self.drop_area.configure(bg=self.BG_PANEL))

        # ── Настройки ─────────────────────────────────────────────────────
        sf = tk.Frame(self.root, bg=self.BG)
        sf.pack(padx=20, pady=6, fill="x")

        # FPS
        tk.Label(sf, text="Кадров/сек:", bg=self.BG, fg=self.FG,
                 font=("Helvetica", 9)).grid(row=0, column=0, sticky="w")
        self.fps_var = tk.StringVar(value=str(self.cfg["fps"]))
        fps_spin = tk.Spinbox(sf, from_=0.1, to=60, increment=0.5,
                              textvariable=self.fps_var, width=6,
                              font=("Helvetica", 9))
        fps_spin.grid(row=0, column=1, padx=(4, 12))

        # Формат
        tk.Label(sf, text="Формат:", bg=self.BG, fg=self.FG,
                 font=("Helvetica", 9)).grid(row=0, column=2, sticky="w")
        self.fmt_var = tk.StringVar(value=self.cfg["format"])
        fmt_menu = tk.OptionMenu(sf, self.fmt_var, "png", "jpg")
        fmt_menu.config(bg=self.BG_PANEL, fg=self.FG, font=("Helvetica", 9),
                        highlightthickness=0)
        fmt_menu.grid(row=0, column=3, padx=4)

        # Кнопки — сохранить настройки и обновить программу
        bf = tk.Frame(self.root, bg=self.BG)
        bf.pack(pady=(4, 2))

        tk.Button(
            bf, text="💾 Настройки", bg=self.ACCENT, fg="white",
            font=("Helvetica", 9, "bold"), relief="flat",
            command=self._save_settings
        ).pack(side="left", padx=4)

        self.upd_btn = tk.Button(
            bf, text="⬇️ Обновить", bg=self.ACCENT2, fg="white",
            font=("Helvetica", 9, "bold"), relief="flat",
            command=self._check_update
        )
        self.upd_btn.pack(side="left", padx=4)

        # Лог
        self.log_var = tk.StringVar(value="Жду видео…")
        tk.Label(
            self.root, textvariable=self.log_var,
            bg=self.BG, fg="#888", font=("Helvetica", 9),
            wraplength=340, justify="center"
        ).pack(pady=(4, 8))

    # ── Обработчики ──────────────────────────────────────────────────────
    def _on_drop(self, event):
        # tkinterdnd2 отдаёт пути в фигурных скобках для путей с пробелами
        raw = event.data
        # Убираем обрамляющие фигурные скобки
        path = raw.strip("{}").strip()
        # На Windows иногда приходит несколько — берём первый
        if " " in raw and not raw.startswith("{"):
            path = raw.split()[0]
        self._process(path)

    def _pick_file(self):
        f = filedialog.askopenfilename(
            title="Выбери видео",
            filetypes=[
                ("Видео", "*.mp4 *.avi *.mkv *.mov *.webm *.flv *.wmv *.m4v *.ts"),
                ("Все файлы", "*.*"),
            ]
        )
        if f:
            self._process(f)

    def _process(self, video_path):
        # Обновляем cfg из UI
        try:
            self.cfg["fps"] = float(self.fps_var.get())
        except ValueError:
            self.cfg["fps"] = 1
        self.cfg["format"] = self.fmt_var.get()

        def task():
            try:
                extract_frames(video_path, None, self.cfg, log_fn=self._log)
            except Exception as exc:
                self._log(f"❌ Ошибка: {exc}")

        threading.Thread(target=task, daemon=True).start()

    def _log(self, msg):
        self.root.after(0, lambda: self.log_var.set(msg))

    def _save_settings(self):
        try:
            self.cfg["fps"] = float(self.fps_var.get())
        except ValueError:
            pass
        self.cfg["format"] = self.fmt_var.get()
        save_config(self.cfg)
        self._log("⚙️ Настройки сохранены!")

    # ── Авто-обновление ──────────────────────────────────────────────────
    def _check_update(self):
        if not HAS_UPDATER:
            self._log("⚠️ Модуль обновления не найден (updater.py)")
            return
        self.upd_btn.config(state="disabled")
        self._log("⬇️ Проверяю обновления…")

        def task():
            try:
                upd = Updater(repo_url=REPO_URL, branch=REPO_BRANCH)
                ok, msg = upd.update()
                self._log(("✅ " if ok else "❌ ") + msg)
                if ok and "up to date" not in msg.lower():
                    # Перезапускаем, чтобы подхватить новую версию
                    self.root.after(1200, upd.restart)
            except Exception as exc:
                self._log(f"❌ Ошибка обновления: {exc}")
            finally:
                self.root.after(0, lambda: self.upd_btn.config(state="normal"))

        threading.Thread(target=task, daemon=True).start()


# ── Точка входа ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    App()
