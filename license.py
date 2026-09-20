"""
Лицензия / демо для «Кадрика» — единая модель бренда MAMONOV.

Как это работает:
  * Демо работает 3 дня без ограничений.
  * Номер копии (AF7) привязан К КОНКРЕТНОМУ КОМПЬЮТЕРУ: программа
    считает устойчивый идентификатор машины и отправляет его вместе с номером:
    /api/check.php?instance=<номер>&machine=<ид компьютера> → {"licensed": true/false}.
  * Сайт запоминает пару «номер ↔ компьютер» при первом же обращении,
    поэтому к моменту покупки уже знает, на каком компьютере живёт копия.
    Оплата снимает демо только для этой пары номер+компьютер.
  * Мягкий режим: нет связи — работаем по последнему ответу; один раз получив
    licensed=true — больше не блокируемся.
  * Номер копии — из «хвоста» .exe (метка MAMONOV_ID:AF7) → из
    _COPY_NUMBER (для запуска из исходников).
Зависимости: только стандартные библиотеки Python.
"""

import os
import re
import sys
import json
import time
import hashlib
import platform
import uuid
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen, Request

# Сколько дней работает демо
TRIAL_DAYS = 3

# Сайт, где проверяется покупка
SITE_URL = "https://evgeniymamonov.com"

# Номер копии для запуска из исходников (у собранного exe берётся автоматически)
_COPY_NUMBER = ""

_COPY_RE = re.compile(r"^[A-Z]{2}[0-9]+$")


def _tail_id(exe):
    """Читает метку MAMONOV_ID:XXX из последних 256 байт exe."""
    try:
        data = Path(exe).read_bytes()[-256:]
        marker = b"MAMONOV_ID:"
        i = data.rfind(marker)
        if i >= 0:
            raw = data[i + len(marker):]
            for sep in (b"\x00", b"\r", b"\n", b" "):
                raw = raw.split(sep)[0]
            return raw.decode("ascii", "ignore").strip()
    except Exception:
        pass
    return ""


def copy_number():
    """Номер копии вида AF7: хвост exe → _COPY_NUMBER."""
    if _COPY_NUMBER:
        return _COPY_NUMBER.upper()
    try:
        if getattr(sys, "frozen", False):
            t = (_tail_id(sys.executable) or "").upper()
            if _COPY_RE.match(t):
                return t
    except Exception:
        pass
    return ""


def machine_id():
    """Устойчивый идентификатор этого компьютера (короткий хеш).

    На Windows берём MachineGuid из реестра (самый стабильный ид СИСТЕМЫ),
    плюс имя компьютера. Запасной вариант — MAC-адрес. Возвращает
    16 шестнадцатеричных символов в верхнем регистре — без личных данных.
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


def check_online(copy=None, machine=None, timeout=6):
    """Спрашивает сайт, снята ли демо с этой копии НА ЭТОМ компьютере.
    Передаёт номер копии и ид компьютера — сайт запоминает эту пару.
    Возвращает True / False / None (нет связи или нет номера)."""
    if copy is None:
        copy = copy_number()
    if not _COPY_RE.match(copy or ""):
        return None
    if machine is None:
        machine = machine_id()
    url = SITE_URL + "/api/check.php?" + urlencode({"instance": copy, "machine": machine})
    try:
        req = Request(url, headers={"User-Agent": "Kadrik"})
        with urlopen(req, timeout=timeout) as r:
            obj = json.loads(r.read().decode("utf-8", "ignore") or "{}")
        return bool(obj.get("licensed"))
    except Exception:
        return None


def _state_file(base):
    return Path(base) / ".kadrik_lic"


def _load(base):
    data = {}
    try:
        for line in _state_file(base).read_text(encoding="utf-8").splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                data[k.strip()] = v.strip()
    except Exception:
        pass
    return data


def _save(base, data):
    p = _state_file(base)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(f"{k}={v}" for k, v in data.items()), encoding="utf-8")
        if os.name == "nt":
            try:
                import ctypes
                # 2 = FILE_ATTRIBUTE_HIDDEN
                ctypes.windll.kernel32.SetFileAttributesW(str(p), 2)
            except Exception:
                pass
    except Exception:
        pass


def mark_licensed(base):
    """Запоминает, что копия куплена (больше не блокируем)."""
    st = _load(base)
    st["lic"] = "1"
    _save(base, st)


def status(base):
    """Состояние лицензии по местным данным (без сети).
    Возвращает (state, days_left):
      'activated' — куплена (запомнено);
      'trial'     — демо, осталось days_left дней;
      'expired'   — демо закончилось.
    """
    st = _load(base)
    if st.get("lic") == "1":
        return "activated", 0
    now = int(time.time())
    try:
        first = int(st.get("first", "0"))
    except Exception:
        first = 0
    if first <= 0:
        first = now
        st["first"] = str(first)
        _save(base, st)
    # Защита от перевода часов назад: берём самую позднюю виденную дату.
    try:
        seen = int(st.get("seen", "0"))
    except Exception:
        seen = 0
    ref = max(now, seen)
    if now >= seen:
        st["seen"] = str(now)
        _save(base, st)
    left = TRIAL_DAYS - (ref - first) // 86400
    if left > 0:
        return "trial", int(left)
    return "expired", 0
