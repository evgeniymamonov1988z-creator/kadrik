"""
Лицензия / демо для «Кадрика» — единая модель бренда MAMONOV
(та же схема, что и у «Записи экрана»).

Как это работает — БЕЗ номеров копий:
  * Демо работает 3 дня без ограничений.
  * Одна программа на всё (нет отдельных сборок демо/полная).
  * Программа привязана к ОТПЕЧАТКУ этого компьютера (machine_id):
    16 hex-символов из MachineGuid Windows + имя ПК. Без личных данных.
  * Проверка оплаты по отпечатку:
      /api/check.php?product=AF&machine=<отпечаток> -> {"paid": true/false}
  * Кнопка «Разблокировать» сама подставляет отпечаток в ссылку оплаты —
    покупателю ничего вводить не надо.
  * Локальная «галочка оплачено» — папка %APPDATA%\\MAMONOV\\.license_AF
    с файлом id.txt, где лежит отпечаток ЭТОГО компьютера (чтобы
    папку нельзя было просто скопировать на другой ПК). Есть галочка ->
    полная версия сразу, даже без интернета.
  * Дата первого запуска демо — в %APPDATA%\\MAMONOV\\.demo_date_AF.
  * Защита от перевода часов назад: помним самую позднюю виденную дату.
Зависимости: только стандартные библиотеки Python.
Совместимость: функции status()/check_online()/mark_licensed()/machine_id()
сохранены, чтобы kadrik.py не менялся по вызовам.
"""

import os
import json
import time
import hashlib
import platform
import uuid
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen, Request

# Буквенный код продукта («Кадрик» = AF, как у «Записи экрана» = AE)
PRODUCT_CODE = "AF"

# Сколько дней работает демо
TRIAL_DAYS = 3

# Сайт, где проверяется покупка
SITE_URL = "https://evgeniymamonov.com"

# Скрытая папка бренда в профиле Windows (%APPDATA%\\MAMONOV)
_DEMO_DIR = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")), "MAMONOV")


def machine_id():
    """Устойчивый «отпечаток» этого компьютера (16 hex-символов).

    На Windows — MachineGuid из реестра (самый стабильный ид системы) +
    имя компьютера. Запасной вариант — MAC-адрес. Без личных данных.
    Та же схема, что и у «Записи экрана» — одна копия = один компьютер.
    """
    parts = []
    if os.name == "nt":
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography", 0,
                winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
            try:
                guid, _ = winreg.QueryValueEx(key, "MachineGuid")
            finally:
                winreg.CloseKey(key)
            if guid:
                parts.append(str(guid))
        except Exception:
            pass
    try:
        node = platform.node()
        if node:
            parts.append(node)
    except Exception:
        pass
    if not parts:
        try:
            parts.append(str(uuid.getnode()))
        except Exception:
            pass
    raw = "|".join(p for p in parts if p) or "unknown"
    return hashlib.sha256(raw.encode("utf-8", "ignore")).hexdigest()[:16].upper()


# ---- Локальная «галочка оплачено» (папка с отпечатком) ----

def _license_dir():
    return Path(_DEMO_DIR) / f".license_{PRODUCT_CODE}"


def _has_local_license():
    """Папка-галочка есть и в ней отпечаток именно этого компьютера."""
    try:
        with open(_license_dir() / "id.txt", "r", encoding="utf-8") as f:
            val = (f.read().strip() or "").upper()
        return val == machine_id()
    except Exception:
        return False


def _create_local_license():
    """Создать папку-галочку с отпечатком компьютера внутри."""
    d = _license_dir()
    try:
        d.mkdir(parents=True, exist_ok=True)
        with open(d / "id.txt", "w", encoding="utf-8") as f:
            f.write(machine_id())
        if os.name == "nt":
            try:
                import ctypes
                # 2 = FILE_ATTRIBUTE_HIDDEN
                ctypes.windll.kernel32.SetFileAttributesW(str(d), 2)
            except Exception:
                pass
    except Exception:
        pass


# ---- Состояние демо (дата первого запуска) ----

def _demo_file():
    return Path(_DEMO_DIR) / f".demo_date_{PRODUCT_CODE}"


def _load_demo():
    data = {}
    try:
        for line in _demo_file().read_text(encoding="utf-8").splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                data[k.strip()] = v.strip()
    except Exception:
        pass
    return data


def _save_demo(data):
    p = _demo_file()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(f"{k}={v}" for k, v in data.items()),
                     encoding="utf-8")
        if os.name == "nt":
            try:
                import ctypes
                ctypes.windll.kernel32.SetFileAttributesW(str(p), 2)
            except Exception:
                pass
    except Exception:
        pass


def mark_licensed(base=None):
    """Запомнить, что копия куплена (больше не блокируем).

    Создаёт локальную папку-галочку с отпечатком компьютера — как у
    «Записи экрана». Параметр base оставлен для совместимости.
    """
    _create_local_license()


def status(base=None):
    """Состояние лицензии по местным данным (без сети).
    Возвращает (state, days_left):
      'activated' — куплена (есть локальная галочка с отпечатком);
      'trial'     — демо, осталось days_left дней;
      'expired'   — демо закончилось.
    Параметр base оставлен для совместимости (храним в %APPDATA%\\MAMONOV).
    """
    if _has_local_license():
        return "activated", 0
    now = int(time.time())
    st = _load_demo()
    try:
        first = int(st.get("first", "0"))
    except Exception:
        first = 0
    if first <= 0:
        first = now
        st["first"] = str(first)
        _save_demo(st)
    # Защита от перевода часов назад: берём самую позднюю виденную дату.
    try:
        seen = int(st.get("seen", "0"))
    except Exception:
        seen = 0
    ref = max(now, seen)
    if now >= seen:
        st["seen"] = str(now)
        _save_demo(st)
    left = TRIAL_DAYS - (ref - first) // 86400
    if left > 0:
        return "trial", int(left)
    return "expired", 0


def check_online(copy=None, machine=None, base=None, timeout=6):
    """Спрашивает сайт, оплачен ли этот отпечаток компьютера.
    Отправляет product=AF&machine=<отпечаток>, читает поле "paid".

    Если сайт сказал «оплачено» — сразу создаём локальную галочку,
    чтобы дальше работать даже без интернета.

    Возвращает True / False / None (нет связи или ошибка).
    Параметры copy/base оставлены для совместимости."""
    if machine is None:
        machine = machine_id()
    url = SITE_URL + "/api/check.php?" + urlencode(
        {"product": PRODUCT_CODE, "machine": machine})
    try:
        req = Request(url, headers={"User-Agent": "Kadrik"})
        with urlopen(req, timeout=timeout) as r:
            obj = json.loads(r.read().decode("utf-8", "ignore") or "{}")
        paid = bool(obj.get("paid"))
        if paid:
            _create_local_license()
        return paid
    except Exception:
        return None


def buy_params():
    """Параметры для ссылки оплаты: product=AF&machine=<отпечаток>."""
    return {"product": PRODUCT_CODE, "machine": machine_id()}
