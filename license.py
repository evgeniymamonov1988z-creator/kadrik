"""
Лицензия / демо (v5 — простой локальный таймер, без интернета и привязки).

Две сборки из одного кода:
  * ПОЛНАЯ версия — рядом с .exe НЕТ файла demo.flag → без ограничений.
  * ДЕМО версия  — рядом с .exe лежит demo.flag → 3 дня, потом блок.

Дата первого запуска хранится в двух местах (реестр Windows
+ скрытый файл в %APPDATA%\\MAMONOV); берётся самая ранняя из двух,
чтобы перезапись одного из них не сбрасывала срок. Сервера,
лицензий и отпечатка компьютера больше нет.

Зависимости: только стандартные библиотеки Python.
Публичные функции status()/status_msstore_aware()/buy_params() сохранены,
чтобы kadrik.py не менялся по вызовам.
"""

import os
import sys
import time
import math
import hashlib

# Буквенный код продукта («Кадрик» = AF)
PRODUCT_CODE = "AF"

# Сколько дней работает демо
TRIAL_DAYS = 3

# Сайт (для ссылки на покупку)
SITE_URL = "https://evgeniymamonov.com"

_DEMO_DIR = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")), "MAMONOV")
_DEMO_FILE = os.path.join(_DEMO_DIR, ".demo_date_" + PRODUCT_CODE)


def _app_dirs():
    """Все возможные папки с программой. Под Nuitka __file__
    для субмодуля не указывает на папку с .exe, поэтому
    проверяем sys.executable, sys.argv[0] и __file__."""
    out = []
    cands = [getattr(sys, "executable", None),
             (sys.argv[0] if getattr(sys, "argv", None) else None),
             __file__]
    for p in cands:
        try:
            if p:
                d = os.path.dirname(os.path.abspath(p))
                if d and d not in out:
                    out.append(d)
        except Exception:
            pass
    return out or ["."]


def _app_dir():
    """Папка, где лежит .exe (или .py при запуске из исходника)."""
    try:
        return _app_dirs()[0]
    except Exception:
        return "."


def _is_demo_edition():
    """Демо-сборка? Признак — рядом с программой файл demo.flag.
    Проверяем все возможные папки (.exe / argv[0] / модуль).
    Нет файла → полная версия без ограничений."""
    for d in _app_dirs():
        try:
            if os.path.isfile(os.path.join(d, "demo.flag")):
                return True
        except Exception:
            pass
    return False


def _read_reg_date():
    if os.name != "nt":
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\MAMONOV") as key:
            val, _ = winreg.QueryValueEx(key, "first_" + PRODUCT_CODE)
            return float(val)
    except Exception:
        return None


def _write_reg_date(ts):
    if os.name != "nt":
        return
    try:
        import winreg
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\MAMONOV")
        try:
            winreg.SetValueEx(key, "first_" + PRODUCT_CODE, 0,
                              winreg.REG_SZ, str(ts))
        finally:
            winreg.CloseKey(key)
    except Exception:
        pass


def _read_file_date():
    try:
        with open(_DEMO_FILE, "r", encoding="utf-8") as f:
            return float(f.read().strip())
    except Exception:
        return None


def _write_file_date(ts):
    try:
        os.makedirs(_DEMO_DIR, exist_ok=True)
        with open(_DEMO_FILE, "w", encoding="utf-8") as f:
            f.write(str(ts))
        if os.name == "nt":
            try:
                import ctypes
                ctypes.windll.kernel32.SetFileAttributesW(_DEMO_FILE, 2)
            except Exception:
                pass
    except Exception:
        pass


def _first_run_ts():
    """Самая ранняя сохранённая дата; если нигде нет — сохраняем
    текущую в оба места. Всегда синхронизируем оба самой ранней."""
    now = time.time()
    dates = [d for d in (_read_reg_date(), _read_file_date()) if d]
    first = min(dates) if dates else now
    _write_reg_date(first)
    _write_file_date(first)
    return first


# ---------------------------------------------------------------
# Отметка запуска демо в Яндекс.Метрике (цель «Запуск программы»).
# Один раз на копию открываем служебную страницу в обычном браузере:
# Метрика видит настоящий визит человека и засчитывает цель.
# Тихо: при любой ошибке ничего не происходит.
# ---------------------------------------------------------------
_LAUNCH_PAGE = "https://evgeniymamonov.com/zapusk-af.html"


def _copy_id():
    """Обезличенный номер копии (создаётся один раз, без личных данных)."""
    try:
        os.makedirs(_DEMO_DIR, exist_ok=True)
        f = os.path.join(_DEMO_DIR, ".copy_id_" + PRODUCT_CODE)
        if os.path.isfile(f):
            with open(f, "r", encoding="utf-8") as fh:
                cid = fh.read().strip()
            if cid:
                return cid
        import uuid
        cid = PRODUCT_CODE + str(uuid.uuid4().int)[:9]
        with open(f, "w", encoding="utf-8") as fh:
            fh.write(cid)
        return cid
    except Exception:
        return ""


def _is_owner():
    """Компьютер владельца (файл owner.flag) — запуски не считаем."""
    for d in _app_dirs():
        try:
            if os.path.isfile(os.path.join(d, "owner.flag")):
                return True
        except Exception:
            pass
    try:
        if os.path.isfile(os.path.join(_DEMO_DIR, "owner.flag")):
            return True
    except Exception:
        pass
    return False


def metrika_launch_page():
    """Один раз на копию открыть служебную страницу, чтобы Метрика
    засчитала запуск демо. Повторные запуски окно не открывают."""
    try:
        if not _is_demo_edition() or _is_owner():
            return
        cid = _copy_id()
        if not cid:
            return
        tok = hashlib.sha1((cid + _LAUNCH_PAGE).encode("utf-8")).hexdigest()[:8]
        mark = os.path.join(_DEMO_DIR, ".mh_" + PRODUCT_CODE + "_" + tok)
        if os.path.isfile(mark):
            return
        try:
            with open(mark, "w", encoding="utf-8") as fh:
                fh.write(cid)
        except Exception:
            return
        import threading
        import webbrowser
        threading.Timer(1.5, lambda: webbrowser.open(_LAUNCH_PAGE, new=0, autoraise=False)).start()
    except Exception:
        pass


def evaluate():
    """(state, days_left): 'activated' | 'trial' | 'expired'.
    Полная версия — всегда 'activated'. Демо — 3 дня, потом 'expired'."""
    if not _is_demo_edition():
        return "activated", 0
    remaining = TRIAL_DAYS - (time.time() - _first_run_ts()) / 86400.0
    if remaining <= 0:
        return "expired", 0
    return "trial", max(1, int(math.ceil(remaining)))


def status(base=None):
    """Состояние демо. base — для совместимости."""
    return evaluate()


def status_msstore_aware(base=None):
    """Имя сохранено для совместимости (Microsoft Store больше нет)."""
    return evaluate()


def check_online(copy=None, machine=None, base=None, timeout=6):
    """Сервера больше нет — всегда None. Оставлено для совместимости."""
    return None


def mark_licensed(base=None):
    """Больше ничего не пишем. Оставлено для совместимости."""
    return None


def machine_id():
    """Привязки к компьютеру больше нет. Оставлено для совместимости."""
    return ""


def buy_params():
    """Параметры для ссылки оплаты (без отпечатка компьютера)."""
    return {"product": PRODUCT_CODE}

# ---------------------------------------------------------------
# Статистика запусков (одинаково у Экранника, Кадрика и Диктика).
# При старте демо — один тихий сигнал на сервер + отметка в Метрике.
# На компьютере владельца (owner.flag) ничего не шлётся.
# Ничего не блокирует: при любой ошибке молчит.
# ---------------------------------------------------------------
_PING_URL = "https://evgeniymamonov.com/api/ping.php"


def demo_ping(status="demo", days=0):
    """Один тихий фоновый сигнал: демо-копию запустили."""
    if not _is_demo_edition() or _is_owner():
        return

    def _send():
        try:
            import urllib.parse
            import urllib.request
            cid = _copy_id()
            if not cid:
                return
            q = urllib.parse.urlencode({"instance": cid,
                                        "status": status,
                                        "days": int(days)})
            req = urllib.request.Request(
                _PING_URL + "?" + q,
                headers={"User-Agent": "MAMONOV-DemoPing/1.0"})
            urllib.request.urlopen(req, timeout=3).read()
        except Exception:
            pass

    try:
        import threading
        threading.Thread(target=_send, daemon=True).start()
    except Exception:
        pass


def status_file_path():
    """Путь к файлу-подсказке status_AF.txt рядом с программой."""
    try:
        return os.path.join(_app_dir(), "status_" + PRODUCT_CODE + ".txt")
    except Exception:
        return ""


def write_status_file():
    """Записать понятный статус демо в status_AF.txt (как у других программ)."""
    try:
        import json
        import datetime as _dt
        path = status_file_path()
        if not path:
            return
        state, left = evaluate()
        if state == "activated":
            code, text = "licensed", "\u041f\u043e\u043b\u043d\u0430\u044f \u0432\u0435\u0440\u0441\u0438\u044f"
        elif state == "expired":
            code, text = "expired", "\u0414\u0435\u043c\u043e \u043a\u043e\u043d\u0447\u0438\u043b\u043e\u0441\u044c"
        else:
            code, text = "demo", "\u0414\u0435\u043c\u043e, \u043e\u0441\u0442\u0430\u043b\u043e\u0441\u044c \u0434\u043d\u0435\u0439: %d" % left
        data = {"product": PRODUCT_CODE,
                "status": code,
                "status_text": text,
                "days_left": left,
                "updated": _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def demo_startup():
    """Всё, что нужно сделать при старте демо: статус + сигнал + Метрика."""
    try:
        write_status_file()
    except Exception:
        pass
    try:
        state, left = evaluate()
        demo_ping("demo" if state == "trial" else state,
                  left if state == "trial" else 0)
    except Exception:
        pass
    try:
        metrika_launch_page()
    except Exception:
        pass
