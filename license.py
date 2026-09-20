"""
Лицензия / демо для «Кадрика» — единая модель бренда MAMONOV.

Правила (как у «Записи экрана»):
  * Демо работает 3 дня без ограничений, потом просит ключ активации.
  * Тяжёлую защиту не делаем — программа стоит около $3.
  * Номер копии берётся из имени файла (Kadrik_AF1.exe) → из «хвоста» .exe
    (метка MAMONOV_ID:AF1) → из переменной _COPY_NUMBER (для запуска из исходников).
  * Настоящий секрет в код НЕ кладётся: берётся из переменной окружения
    KADRIK_ACT_SECRET или из файла activation_secret.txt рядом с программой
    (этот файл в .gitignore). На сайте (api/.env) строка должна быть та же.
Зависимости: только стандартные библиотеки Python.
"""

import os
import sys
import time
import hmac
import base64
import hashlib
from pathlib import Path

# Сколько дней работает демо
TRIAL_DAYS = 3

# Буква-код программы (как AE у «Записи экрана»). Задаётся при запуске из
# исходников. У собранного exe номер берётся из имени файла / хвоста exe.
_COPY_NUMBER = ""

# Запасной секрет только для отладки. НА ПРОДАЖЕ замените его своим
# длинным случайным секретом через activation_secret.txt / переменную окружения.
_FALLBACK_SECRET = "KADRIK-DEMO-SECRET-CHANGE-ME"


def _app_dir():
    """Папка, где лежит программа (exe или исходник)."""
    try:
        if getattr(sys, "frozen", False):
            return Path(sys.executable).parent
        return Path(__file__).resolve().parent
    except Exception:
        return Path.cwd()


def _secret():
    """Секрет для ключей: переменная окружения → файл рядом → запасной."""
    env = os.environ.get("KADRIK_ACT_SECRET", "").strip()
    if env:
        return env
    try:
        f = _app_dir() / "activation_secret.txt"
        if f.exists():
            s = f.read_text(encoding="utf-8").strip()
            if s:
                return s
    except Exception:
        pass
    return _FALLBACK_SECRET


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
    """Номер копии: имя файла → хвост exe → _COPY_NUMBER."""
    if _COPY_NUMBER:
        return _COPY_NUMBER.upper()
    try:
        if getattr(sys, "frozen", False):
            exe = sys.executable
            stem = Path(exe).stem
            if "_" in stem:
                tail = stem.rsplit("_", 1)[1]
                if tail and tail.isalnum():
                    return tail.upper()
            t = _tail_id(exe)
            if t:
                return t.upper()
    except Exception:
        pass
    return ""


def expected_key(cn=None):
    """Ключ активации для номера копии (формат XXXX-XXXX-XXXX-XXXX)."""
    if cn is None:
        cn = copy_number()
    msg = (cn or "NOID").encode("utf-8")
    dig = hmac.new(_secret().encode("utf-8"), msg, hashlib.sha256).digest()
    code = base64.b32encode(dig).decode("ascii").rstrip("=")[:16]
    return "-".join(code[i:i + 4] for i in range(0, 16, 4))


def check_key(key):
    """Проверяет введённый ключ."""
    k = (key or "").strip().upper().replace(" ", "")
    if not k:
        return False
    return hmac.compare_digest(k, expected_key())


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


def status(base):
    """Состояние лицензии.
    Возвращает (state, days_left):
      'activated' — куплена;
      'trial'     — демо, осталось days_left дней;
      'expired'   — демо закончилось.
    """
    st = _load(base)
    if st.get("act") == "1":
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
    # Защита от перевода часов назад: если видим более позднюю «последнюю» дату — берём её.
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


def activate(base, key):
    """Проверяет ключ и, если верный, сохраняет активацию."""
    if check_key(key):
        st = _load(base)
        st["act"] = "1"
        st["key"] = (key or "").strip().upper().replace(" ", "")
        _save(base, st)
        return True
    return False
