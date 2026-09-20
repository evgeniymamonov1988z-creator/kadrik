"""
Лицензия / демо для «Кадрика» — единая модель бренда MAMONOV.

Как у «Записи экрана»:
  * Демо работает 3 дня без ограничений.
  * После покупки демо снимается ОНЛАЙН: программа спрашивает сайт
    /api/check.php?instance=<номер копии> → {"licensed": true/false}.
    Когда оплата прошла, номер копии попадает в licensed.txt на сайте.
  * Мягкий режим: нет связи — работаем по последнему ответу; один раз получив
    licensed=true — больше не блокируемся.
  * Номер копии — из имени файла (Kadrik_AF7.exe) → из «хвоста» .exe
    (метка MAMONOV_ID:AF7) → из _COPY_NUMBER (для запуска из исходников).
Зависимости: только стандартные библиотеки Python.
"""

import os
import re
import sys
import json
import time
from pathlib import Path
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
    """Номер копии вида AF7: имя файла → хвост exe → _COPY_NUMBER."""
    if _COPY_NUMBER:
        return _COPY_NUMBER.upper()
    try:
        if getattr(sys, "frozen", False):
            exe = sys.executable
            stem = Path(exe).stem
            if "_" in stem:
                tail = stem.rsplit("_", 1)[1].upper()
                if _COPY_RE.match(tail):
                    return tail
            t = (_tail_id(exe) or "").upper()
            if _COPY_RE.match(t):
                return t
    except Exception:
        pass
    return ""


def check_online(copy=None, timeout=6):
    """Спрашивает сайт, снята ли демо с этой копии.
    Возвращает True / False / None (нет связи или нет номера)."""
    if copy is None:
        copy = copy_number()
    if not _COPY_RE.match(copy or ""):
        return None
    url = SITE_URL + "/api/check.php?instance=" + copy
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
