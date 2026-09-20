"""
Kadrik / Кадрик — видео → кадры (фото).
Маленький квадрат с чёрным квадратом в центре: перетаскиваешь видео → программа режет его на кадры.
Язык: на российской Windows — по-русски, на остальных — по-английски.
Зависимости: tkinter (встроен), ffmpeg (системный), tkinterdnd2 (опционально для drag-and-drop).
"""

import os
import sys
import time
import locale
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog
from pathlib import Path

# Модуль авто-загрузки инструментов (только стандартные библиотеки) — подключаем раньше всех,
# чтобы сразу добавить папку bin/ в пути и грузить библиотеки оттуда.
# Сначала гарантируем, что папка с этим файлом видна Python — иначе из другой папки модуль не найдётся.
try:
    if getattr(sys, "frozen", False):
        _here = os.path.dirname(sys.executable)
    else:
        _here = os.path.dirname(os.path.abspath(__file__))
    if _here and _here not in sys.path:
        sys.path.insert(0, _here)
except Exception:
    pass

try:
    import tools_setup
    tools_setup.add_to_path()
    HAS_SETUP = True
except Exception:
    HAS_SETUP = False

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

# Лицензия / демо (единая модель бренда: 3 дня демо, потом ключ активации)
try:
    import license as lic
    HAS_LIC = True
except Exception:
    HAS_LIC = False

# Pillow — нужен только для режима «самые чёткие кадры» (оценка резкости)
try:
    from PIL import Image, ImageFilter, ImageStat
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# Пути к движку нарезки. По умолчанию — системные; при запуске могут смениться на скачанные.
FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"

# Чтобы при вызове ffmpeg/ffprobe на Windows не выскакивало чёрное окно консоли.
_NOWIN = {"creationflags": 0x08000000} if os.name == "nt" else {}


def _hide_console():
    """Прячет чёрное окно консоли, если оно появилось за программой (только Windows)."""
    if os.name != "nt":
        return
    try:
        import ctypes
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # 0 = SW_HIDE
    except Exception:
        pass


# Прячем консоль как можно раньше — ещё до открытия окна.
_hide_console()


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

# Передаём язык модулю загрузки, чтобы его сообщения в журнале были на нужном языке.
if HAS_SETUP:
    try:
        tools_setup.set_lang(LANG)
    except Exception:
        pass

# Строки интерфейса (везде с большой буквы)
STRINGS = {
    "ru": {
        "app":        "Кадрик",
        "drop":       "Перетащи\nВидео",
        "update":     "Обновить",
        "wait":       "Жду видео…",
        "cutting":    "Нарезаю кадры…",
        "scenes":     "Ищу сцены…",
        "ranking":    "Выбираю чёткие кадры…",
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
        # Понятные подсказки при ошибках
        "e_nogit":  "Нужен Git.\nСкачай: git-scm.com",
        "e_net":    "Нет интернета",
        "e_fail":   "Не вышло обновить",
        "copied":   "✓ Скопировано",
        # Первый запуск — загрузка движка
        "prep":     "Первый запуск: готовлю программу…",
        "ready":    "Готово к работе",
        "no_ff":    "Нет движка видео.\nНужен интернет",
        "old_ver":  "Старая версия: нет авто-загрузки",
        # Демо / активация
        "trial_left":  "Демо: осталось {n} дн.",
        "demo_over":   "Демо закончилось",
        "buy_at":      "Купить: evgeniymamonov.com",
        "checking_lic":"Проверяю покупку…",
        "recheck":     "Проверить снова",
        "not_yet":     "Пока не найдено.\nПосле оплаты нажмите «Проверить снова».",
        "act_ok":      "Спасибо! Полная версия.",
        "already_running": "Кадрик уже запущен",
    },
    "en": {
        "app":        "Kadrik",
        "drop":       "Drop\nVideo",
        "update":     "Update",
        "wait":       "Waiting For Video…",
        "cutting":    "Extracting Frames…",
        "scenes":     "Detecting Scenes…",
        "ranking":    "Picking Sharp Frames…",
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
        "e_nogit":  "Git required.\nGet it: git-scm.com",
        "e_net":    "No internet",
        "e_fail":   "Update failed",
        "copied":   "✓ Copied",
        "prep":     "First run: preparing app…",
        "ready":    "Ready",
        "no_ff":    "No video engine.\nInternet needed",
        "old_ver":  "Old version: no auto-download",
        # Demo / activation
        "trial_left":  "Demo: {n} Days Left",
        "demo_over":   "Demo Expired",
        "buy_at":      "Buy: evgeniymamonov.com",
        "checking_lic":"Checking Purchase…",
        "recheck":     "Check Again",
        "not_yet":     "Not Found Yet.\nAfter Payment Click Check Again.",
        "act_ok":      "Thank You! Full Version.",
        "already_running": "Kadrik Is Already Running",
    },
}


def T(key, **kw):
    s = STRINGS[LANG].get(key, key)
    return s.format(**kw) if kw else s


def _friendly(msg):
    """Превращает технический ответ модуля обновления в понятный текст."""
    low = (msg or "").lower()
    if "not installed" in low or "git is not" in low:
        return T("e_nogit")
    if "timeout" in low or "internet" in low or "could not resolve" in low or "unable to access" in low:
        return T("e_net")
    # Известные короткие ответы переводим через словарь, иначе — общая ошибка
    if msg in STRINGS[LANG]:
        return T(msg)
    if low.startswith("already") or "up to date" in low or "updated" in low or "connected" in low:
        return T(msg)
    return T("e_fail")


# Куда складываем кадры: папка Mamonov на Рабочем столе, внутри — подпапка kadrik.
# Если Рабочий стол не найден — используем домашнюю папку. Папки создаются сами.
def _desktop_dir():
    d = Path.home() / "Desktop"
    if d.exists():
        return d
    # Некоторые системы называют папку по-русски
    ru = Path.home() / "Рабочий стол"
    if ru.exists():
        return ru
    return d  # создастся автоматически как Desktop

BASE_DIR = _desktop_dir() / "Mamonov" / "kadrik"

# Репозиторий для авто-обновления (SourceCraft, HTTPS — чтение без ключей/паролей)
REPO_URL = "https://git.sourcecraft.dev/evgeniymamonov1988/kadrik.git"
REPO_BRANCH = "main"

# Сайт для покупки полной версии
SITE_URL = "https://evgeniymamonov.com"

# Настройки по умолчанию (умный режим)
CFG = {
    "format": "png",       # png / jpg
    "quality": 95,          # качество jpg (1-100), для png не используется
    "scene_cap": 100,       # шаг 1: берём по одному кадру на сцену, но не больше стольки
    "keep_sharpest": 20,    # шаг 2: из них оставляем столько самых чётких
    "scene_thresh": 0.3,    # чувствительность к смене сцены (0..1, меньше = больше сцен)
    "fps": 1,               # запасное значение для аварийного режима
}


def _pillow():
    """Возвращает модули Pillow для оценки чёткости или None."""
    try:
        from PIL import Image, ImageFilter, ImageStat
        return Image, ImageFilter, ImageStat
    except Exception:
        return None


def _detect_scene_times(video_path, thresh):
    """Секунды, где меняется сцена (через ffmpeg)."""
    times = []
    try:
        cmd = [FFMPEG, "-i", str(video_path), "-vf",
               f"select='gt(scene,{thresh})',metadata=print",
               "-an", "-f", "null", "-"]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600, **_NOWIN)
        for line in (r.stderr or "").splitlines():
            if "pts_time:" in line:
                try:
                    times.append(float(line.split("pts_time:")[1].split()[0]))
                except Exception:
                    pass
    except Exception:
        pass
    return times


def _sharpness(path, Image, ImageFilter, ImageStat):
    """Оценка чёткости кадра: чем больше, тем чётче (вариация Лапласа)."""
    try:
        im = Image.open(path).convert("L")
        im.thumbnail((640, 640))
        lap = ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], scale=1, offset=0)
        edges = im.filter(lap)
        w, h = edges.size
        if w > 4 and h > 4:
            edges = edges.crop((2, 2, w - 2, h - 2))
        return ImageStat.Stat(edges).var[0]
    except Exception:
        return -1.0


def _extract_at(video_path, t, dst, ext, quality):
    """Достаёт один кадр на секунде t."""
    cmd = [FFMPEG, "-ss", f"{t:.3f}", "-i", str(video_path), "-frames:v", "1"]
    if ext in ("jpg", "jpeg"):
        cmd += ["-q:v", str(max(1, min(31, int(31 - quality * 30 / 100))))]
    cmd += [str(dst), "-y"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180, **_NOWIN)
        return r.returncode == 0 and Path(dst).exists()
    except Exception:
        return False


def _video_duration(video_path):
    """Длительность видео в секундах через ffprobe. None — если не узнали."""
    try:
        r = subprocess.run(
            [FFPROBE, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)],
            capture_output=True, text=True, timeout=30, **_NOWIN)
        d = float((r.stdout or "").strip())
        return d if d > 0 else None
    except Exception:
        return None


def extract_frames(video_path, output_dir, cfg, log_fn=None):
    """Умная нарезка: шаг 1 — по кадру на каждую новую сцену (до scene_cap),
    шаг 2 — из них оставляем keep_sharpest самых чётких."""
    fmt = cfg["format"]
    quality = cfg["quality"]

    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(video_path)

    # Кадры складываем прямо в папку на Рабочем столе: Mamonov/kadrik (папки создаются сами).
    if not output_dir:
        output_dir = BASE_DIR
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    ext = fmt if fmt in ("png", "jpg", "jpeg") else "png"

    # Имена файлов делаем уникальными: имя видео + время нарезки,
    # чтобы кадры от разных видео (и повторных нарезок) не затирали друг друга.
    import re as _re
    safe = _re.sub(r'[\\/:*?"<>|]+', "_", video_path.stem).strip() or "video"
    prefix = f"{safe}_{time.strftime('%H%M%S')}"

    scene_cap = int(cfg.get("scene_cap", 100) or 100)
    keep = int(cfg.get("keep_sharpest", 20) or 20)
    duration = _video_duration(video_path)
    pil = _pillow()

    import shutil as _sh

    def _clear_old():
        # Ничего не удаляем — все прежние кадры сохраняются.
        pass

    def _save_ordered(items):
        """items: список (время, путь) — сохраняем по порядку времени."""
        items = sorted(items, key=lambda x: x[0])
        for i, (_t, p) in enumerate(items, 1):
            dst = output_dir / f"{prefix}_{i:04d}.{ext}"
            try:
                Path(p).replace(dst)
            except Exception:
                pass
        return len(items)

    # -------- УМНЫЙ РЕЖИМ --------
    if pil and duration:
        thresh = float(cfg.get("scene_thresh", 0.3))

        # Шаг 1: находим смены сцен, берём по кадру на каждую (до scene_cap штук)
        if log_fn:
            log_fn(T("scenes"))
        scene_times = _detect_scene_times(video_path, thresh)
        cand = [0.0] + [t for t in scene_times if t > 0.5]
        # Всегда добавляем равномерную сетку кадров по всему видео —
        # чтобы был хороший запас даже когда смен сцен нет (статичное видео).
        pool = min(max(keep * 3, 40), scene_cap)
        if pool > 1:
            step = duration / (pool + 1)
            cand += [round(step * i, 2) for i in range(1, pool + 1)]
        cand = sorted(set(round(x, 2) for x in cand))
        # если сцен больше лимита — равномерно прореживаем до scene_cap
        if len(cand) > scene_cap:
            idx = sorted(set(round(i * (len(cand) - 1) / (scene_cap - 1)) for i in range(scene_cap)))
            cand = [cand[i] for i in idx]

        # Шаг 2: достаём кадры-сцены, меряем чёткость, оставляем keep самых чётких
        if log_fn:
            log_fn(T("ranking"))
        tmp = output_dir / "_cand"
        _sh.rmtree(tmp, ignore_errors=True)
        tmp.mkdir(parents=True, exist_ok=True)
        scored = []
        for i, t in enumerate(cand):
            p = tmp / f"c_{i:05d}.{ext}"
            if _extract_at(video_path, t, p, ext, quality):
                scored.append((_sharpness(p, *pil), t, p))

        if scored:
            scored.sort(key=lambda x: x[0], reverse=True)
            best = scored[:keep]
            n = _save_ordered([(t, p) for _s, t, p in best])
            _sh.rmtree(tmp, ignore_errors=True)
            if log_fn:
                log_fn(T("done", n=n))
            return output_dir
        _sh.rmtree(tmp, ignore_errors=True)

    # -------- АВАРИЙНЫЙ РЕЖИМ (нет Pillow / не узнали длину / сцены не нашлись) --------
    # Ровно keep кадров, равномерно по всему видео.
    if log_fn:
        log_fn(T("cutting"))
    pattern = output_dir / f"{prefix}_%04d.{ext}"
    if duration:
        use_fps = min(keep / duration, 30.0)
    else:
        use_fps = cfg.get("fps", 1)
    cmd = [FFMPEG, "-i", str(video_path), "-vf", f"fps={use_fps}"]
    if ext in ("jpg", "jpeg"):
        cmd += ["-q:v", str(max(1, min(31, int(31 - quality * 30 / 100))))]
    else:
        cmd += ["-compression_level", "5"]
    cmd += ["-frames:v", str(keep), str(pattern), "-y"]

    result = subprocess.run(cmd, capture_output=True, text=True, **_NOWIN)
    if result.returncode != 0:
        if log_fn:
            log_fn(T("err_ffmpeg"))
        raise RuntimeError(result.stderr[:300])

    files = sorted(output_dir.glob(f"{prefix}_*.{ext}"))
    if log_fn:
        log_fn(T("done", n=len(files)))
    return output_dir


class App:
    BG      = "#2b2b2b"
    FG      = "#d4d4d4"
    ACCENT  = "#61afef"

    def __init__(self):
        self.cfg = dict(CFG)
        self.ready = False  # готов ли движок нарезки
        self.lic_state = "activated"  # activated / trial / expired
        self.lic_left = 0

        # Перетаскивание нужно подключить ДО создания окна — иначе оно не заработает.
        # Если библиотеки нет — быстро догружаем её и подключаем сразу.
        global HAS_DND, DND_FILES, TkinterDnD
        if not HAS_DND and HAS_SETUP:
            try:
                if tools_setup.ensure_dnd():
                    from tkinterdnd2 import DND_FILES as _D, TkinterDnD as _T
                    DND_FILES, TkinterDnD = _D, _T
                    HAS_DND = True
            except Exception:
                pass

        self.root = TkinterDnD.Tk() if HAS_DND else tk.Tk()
        self.root.title(T("app"))
        self.root.geometry("220x300")
        self.root.configure(bg=self.BG)
        self.root.resizable(False, False)

        # Иконка окна (логотип MAMONOV), если файл рядом есть
        try:
            _ico = os.path.join(_here, "icon.ico")
            if os.path.exists(_ico):
                self.root.iconbitmap(_ico)
        except Exception:
            pass

        # Всегда поверх всех окон
        self.root.attributes("-topmost", True)
        # Сворачивается только по кнопке «_» (штатное поведение окна)

        self._build_ui()

        # Проверяем демо/лицензию и при необходимости показываем окно активации
        self._check_license()

        if HAS_DND:
            self.drop_area.drop_target_register(DND_FILES)
            self.drop_area.dnd_bind("<<Drop>>", self._on_drop)

        # При первом запуске догружаем движок (ffmpeg) в фоне
        threading.Thread(target=self._prepare, daemon=True).start()

        self.root.mainloop()

    def _prepare(self):
        """Проверяет/догружает ffmpeg и Pillow. Запускается в фоне."""
        global FFMPEG, FFPROBE, HAS_PIL
        if not HAS_SETUP:
            # Нет модуля загрузки — пробуем системный ffmpeg
            import shutil as _sh
            if _sh.which("ffmpeg") and _sh.which("ffprobe"):
                self.ready = True
                self._log(T("wait"))
            else:
                self.ready = False
                self._log("❗ " + T("old_ver"))
            return
        # Уже есть?
        ffm, ffp = tools_setup.find_tools()
        if not (ffm and ffp):
            self._log(T("prep"))
            ffm, ffp = tools_setup.ensure_ffmpeg(log_fn=self._log)
        if ffm and ffp:
            FFMPEG, FFPROBE = ffm, ffp
            # догружаем в bin/ остальные библиотеки
            if not HAS_PIL:
                HAS_PIL = tools_setup.ensure_pillow(log_fn=self._log)
            # перетаскивание (опционально; подхватится при следующем запуске)
            if not HAS_DND:
                tools_setup.ensure_dnd(log_fn=self._log)
            self.ready = True
            self._log(T("ready"))
            self._log(T("wait"))
        else:
            # не смогли найти/скачать ffmpeg
            self.ready = False
            self._log("❌ " + T("no_ff"))

    def _build_ui(self):
        tk.Label(
            self.root, text=T("app"),
            bg=self.BG, fg=self.ACCENT, font=("Helvetica", 14, "bold")
        ).pack(pady=(10, 2))

        # Постоянная строка состояния демо (всегда на виду)
        self.demo_lbl = tk.Label(
            self.root, text="", bg=self.BG, fg="#e5c07b",
            font=("Helvetica", 8, "bold"),
        )
        self.demo_lbl.pack(pady=(0, 4))

        # Чёрный квадрат в центре — сюда перетаскивается видео
        self.drop_area = tk.Label(
            self.root,
            text=T("drop"),
            bg="#000000", fg="#777777",
            font=("Helvetica", 10),
            width=11, height=5,
        )
        self.drop_area.pack()
        self.drop_area.bind("<Button-1>", lambda e: self._pick_file())
        self.drop_area.bind("<Enter>", lambda e: self.drop_area.configure(bg="#111111"))
        self.drop_area.bind("<Leave>", lambda e: self.drop_area.configure(bg="#000000"))

        # Журнал лога — клик мышкой копирует весь текст
        log_wrap = tk.Frame(self.root, bg=self.BG)
        log_wrap.pack(fill="both", expand=True, padx=8, pady=(10, 8))

        scroll = tk.Scrollbar(log_wrap)
        scroll.pack(side="right", fill="y")

        self.log_box = tk.Text(
            log_wrap, height=2, wrap="word",
            bg="#1e1e1e", fg="#9fbfdf", font=("Helvetica", 8),
            relief="flat", bd=0, padx=4, pady=3,
            state="disabled", cursor="hand2",
            yscrollcommand=scroll.set,
        )
        self.log_box.pack(side="left", fill="both", expand=True)
        scroll.config(command=self.log_box.yview)

        # Клик левой кнопкой — скопировать весь журнал в буфер обмена
        self.log_box.bind("<Button-1>", self._copy_log)

        self._log(T("wait"))

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
        if self.lic_state == "expired":
            # Демо закончилось — нарезка заблокирована, предлагаем активацию
            self._log(T("demo_over"))
            self._show_activation()
            return
        if not self.ready:
            # движок ещё готовится/не скачался
            if HAS_SETUP and not tools_setup.find_tools()[0]:
                self._log(T("prep"))
                return
        def task():
            try:
                extract_frames(video_path, None, self.cfg, log_fn=self._log)
            except Exception as exc:
                self._log(T("err", e=exc))
        threading.Thread(target=task, daemon=True).start()

    def _log(self, msg):
        """Добавить строку в журнал (с временем), прокрутить вниз."""
        def _append():
            ts = time.strftime("%H:%M:%S")
            self.log_box.config(state="normal")
            self.log_box.insert("end", f"[{ts}] {msg}\n")
            self.log_box.see("end")
            self.log_box.config(state="disabled")
        self.root.after(0, _append)

    def _copy_log(self, event=None):
        """Скопировать весь текст журнала в буфер обмена по клику."""
        text = self.log_box.get("1.0", "end").strip()
        if not text:
            return "break"
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        # Короткая подсказка в заголовке окна
        self.root.title(T("copied"))
        self.root.after(1000, lambda: self.root.title(T("app")))
        return "break"

    # -------- Демо / активация --------
    def _check_license(self):
        """Определяет состояние демо и реагирует."""
        if not HAS_LIC:
            self.lic_state = "activated"
            self._set_demo_label()
            return
        try:
            state, left = lic.status(BASE_DIR)
        except Exception:
            state, left = "activated", 0
        self.lic_state = state
        self.lic_left = left
        self._set_demo_label()
        # Закрепляем постоянный номер копии за этим компьютером (один раз).
        try:
            lic.copy_for(BASE_DIR)
        except Exception:
            pass
        if state == "trial":
            self._log(T("trial_left", n=left))
            # Тихо в фоне спрашиваем сайт — вдруг копия уже куплена
            threading.Thread(target=self._online_check, args=(False,), daemon=True).start()
        elif state == "expired":
            self._log(T("demo_over"))
            # Пробуем снять демо онлайн; если нет — покажем окно покупки
            threading.Thread(target=self._online_check, args=(True,), daemon=True).start()

    def _online_check(self, show_if_locked):
        """Спрашивает сайт, куплена ли копия (в фоне)."""
        try:
            result = lic.check_online(base=BASE_DIR)
        except Exception:
            result = None
        if result is True:
            try:
                lic.mark_licensed(BASE_DIR)
            except Exception:
                pass
            self.lic_state = "activated"
            self._log(T("act_ok"))
            self.root.after(0, self._set_demo_label)
            self.root.after(0, self._close_activation)
        elif show_if_locked:
            # не куплено или нет связи — предлагаем купить
            self.root.after(0, self._show_activation)

    def _close_activation(self):
        win = getattr(self, "_act_win", None)
        try:
            if win is not None and tk.Toplevel.winfo_exists(win):
                win.destroy()
        except Exception:
            pass

    def _set_demo_label(self):
        """Обновляет постоянную строку состояния демо."""
        try:
            if self.lic_state == "trial":
                self.demo_lbl.config(text=T("trial_left", n=self.lic_left), fg="#e5c07b")
            elif self.lic_state == "expired":
                self.demo_lbl.config(text=T("demo_over"), fg="#e06c75")
            else:
                self.demo_lbl.config(text="")
        except Exception:
            pass

    def _show_activation(self):
        """Окно: демо закончилось — ссылка на покупку и кнопка «Проверить снова»."""
        if getattr(self, "_act_win", None) and tk.Toplevel.winfo_exists(self._act_win):
            self._act_win.lift()
            return
        win = tk.Toplevel(self.root)
        self._act_win = win
        win.title(T("demo_over"))
        win.configure(bg=self.BG)
        win.resizable(False, False)
        win.attributes("-topmost", True)
        win.geometry("270x200")

        tk.Label(win, text=T("demo_over"), bg=self.BG, fg=self.ACCENT,
                 font=("Helvetica", 12, "bold")).pack(pady=(14, 6))

        # Ссылка на покупку (клик открывает сайт)
        link = tk.Label(win, text=T("buy_at"), bg=self.BG, fg="#9fbfdf",
                        font=("Helvetica", 10, "underline"), cursor="hand2")
        link.pack(pady=(0, 10))
        link.bind("<Button-1>", lambda e: self._open_site())

        msg = tk.Label(win, text="", bg=self.BG, fg="#98c379",
                       font=("Helvetica", 8), justify="center")
        msg.pack()

        def _recheck(_e=None):
            msg.config(text=T("checking_lic"), fg="#9fbfdf")

            def _job():
                try:
                    res = lic.check_online(base=BASE_DIR)
                except Exception:
                    res = None
                if res is True:
                    try:
                        lic.mark_licensed(BASE_DIR)
                    except Exception:
                        pass
                    self.lic_state = "activated"
                    self._log(T("act_ok"))
                    self.root.after(0, self._set_demo_label)
                    self.root.after(0, self._close_activation)
                else:
                    self.root.after(0, lambda: msg.config(text=T("not_yet"), fg="#e5c07b"))

            threading.Thread(target=_job, daemon=True).start()

        tk.Button(win, text=T("recheck"), command=_recheck,
                  bg=self.ACCENT, fg="#000000", relief="flat",
                  activebackground="#7cc0f5").pack(pady=(10, 12), ipadx=8)

    def _open_site(self):
        try:
            import webbrowser
            webbrowser.open(SITE_URL)
        except Exception:
            self._log(T("buy_at"))


# Защита от повторного запуска: держим файл-блокировку открытым весь сеанс.
_LOCK_HANDLE = None


def _acquire_single_instance():
    """Не даёт запустить вторую копию программы.
    True  — это единственный запущенный экземпляр;
    False — программа уже запущена."""
    global _LOCK_HANDLE
    try:
        BASE_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    lock_path = BASE_DIR / ".kadrik.lock"
    try:
        fh = open(lock_path, "a+")
    except Exception:
        # Не смогли создать файл-замок — не мешаем запуску.
        return True
    try:
        if os.name == "nt":
            import msvcrt
            try:
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                fh.close()
                return False
        else:
            import fcntl
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                fh.close()
                return False
    except Exception:
        # Блокировка недоступна — не мешаем запуску.
        return True
    _LOCK_HANDLE = fh  # держим открытым, пока работает программа
    return True


if __name__ == "__main__":
    if not _acquire_single_instance():
        # Программа уже запущена — короткое сообщение и выход.
        try:
            from tkinter import messagebox as _mb
            _r = tk.Tk()
            _r.withdraw()
            _r.attributes("-topmost", True)
            _mb.showinfo(T("app"), T("already_running"))
            _r.destroy()
        except Exception:
            pass
        sys.exit(0)
    App()
