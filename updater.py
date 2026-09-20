"""
updater.py — универсальный шаблон обновления через Git-репозиторий.

Подключает папку с программой к Git-репозиторию, обновляет (pull),
показывает статусы и ошибки. Работает с pythonw (без консоли).

КАК ИСПОЛЬЗОВАТЬ:
1. Скопируй updater.py в папку с программой
2. В своей программе добавь:

   from updater import Updater
   upd = Updater(
       repo_url="https://oauth2:ВАШ_ТОКЕН@git.example.com/user/repo.git",
       branch="master",
   )
   ok, msg = upd.update()
   # ok = True/False, msg = текст статуса

3. Для кнопки обновления в GUI:
   ok, msg = upd.update()
   label.config(text=msg, fg="green" if ok else "red")
   if ok:
       upd.restart()

4. Можно только подключить (без обновления):
   ok, msg = upd.connect()

НАСТРОЙКА:
- repo_url: адрес репозитория (с токеном или без)
- branch: ветка (по умолчанию master)
- app_dir: папка программы (по умолчанию — где лежит updater.py)
- ssl_verify: проверка SSL (по умолчанию False, для самоподписанных сертификатов)
"""

import os
import sys
import subprocess
import shutil


class Updater:
    """Универсальный обновлятор через Git."""

    def __init__(self, repo_url, branch="master", app_dir=None, ssl_verify=False):
        self.repo_url = repo_url
        self.branch = branch
        self.ssl_verify = ssl_verify
        self.app_dir = app_dir or os.path.dirname(os.path.abspath(
            sys.executable if getattr(sys, 'frozen', False) else __file__))

    def _git(self, *args):
        """Запуск git. Возвращает (returncode, stdout, stderr)."""
        cmd = ["git"]
        if not self.ssl_verify:
            cmd += ["-c", "http.sslVerify=false"]
        cmd += ["-c", "core.autocrlf=false"]
        # Отключаем credential helper — используем токен из URL
        cmd += ["-c", "credential.helper="]
        cmd += list(args)
        try:
            r = subprocess.run(cmd, cwd=self.app_dir, capture_output=True, text=True, timeout=60)
            return r.returncode, r.stdout.strip(), r.stderr.strip()
        except FileNotFoundError:
            return -1, "", "Git is not installed (git-scm.com)"
        except subprocess.TimeoutExpired:
            return -2, "", "Timeout — check internet"
        except Exception as e:
            return -3, "", str(e)

    def _is_repo(self):
        """Папка уже Git-репозиторий?"""
        return os.path.isdir(os.path.join(self.app_dir, ".git"))

    def connect(self):
        """Подключить папку к репозиторию (git init + fetch + reset).
        Возвращает (True/False, сообщение)."""
        # Проверяем git
        rc, _, err = self._git("--version")
        if rc != 0:
            return False, err or "git is not installed"

        # Уже подключено?
        if self._is_repo():
            return True, "Already connected"

        # init
        rc, _, err = self._git("init")
        if rc != 0:
            return False, f"git init failed: {err}"

        # remote add
        rc, _, err = self._git("remote", "add", "origin", self.repo_url)
        if rc != 0:
            self._cleanup_git()
            return False, f"remote add failed: {err}"

        # fetch
        rc, _, err = self._git("fetch", "origin", self.branch)
        if rc != 0:
            self._cleanup_git()
            return False, f"fetch failed: {err}"

        # checkout branch
        self._git("checkout", "-b", self.branch)

        # reset на версию из репо
        rc, _, err = self._git("reset", "--hard", f"origin/{self.branch}")
        if rc != 0:
            self._cleanup_git()
            return False, f"reset failed: {err}"

        return True, "Connected!"

    def update(self):
        """Обновить программу из репозитория.
        Если репозиторий не подключён — подключит автоматически.
        Возвращает (True/False, сообщение)."""

        # Проверяем git
        rc, _, err = self._git("--version")
        if rc != 0:
            return False, err or "git is not installed"

        # Не подключено — подключаем
        if not self._is_repo():
            ok, msg = self.connect()
            if not ok:
                return False, msg
            return True, "Connected and updated!"

        # Уже подключено — обновляем
        self._git("remote", "set-url", "origin", self.repo_url)

        # Убираем незакоммиченные файлы, чтобы не мешали pull
        self._git("checkout", "--", ".")
        # НЕ делаем git clean -fd — он удаляет bin/, lib/, updater.py
        # и все остальные локальные файлы, которых нет в репозитории!

        rc, out, err = self._git("pull", "--rebase", "origin", self.branch)
        if rc != 0:
            # Конфликт — жёсткий сброс до версии из репо
            self._git("fetch", "origin", self.branch)
            self._git("reset", "--hard", f"origin/{self.branch}")
            rc2, out2, err2 = self._git("pull", "origin", self.branch)
            if rc2 != 0:
                return False, f"Update failed: {err}"

        if "Already up to date" in out or "Already up-to-date" in out:
            return True, "Already up to date"

        return True, "Updated!"

    def restart(self):
        """Перезапустить текущую программу."""
        exe = sys.executable
        script = os.path.abspath(sys.argv[0])
        subprocess.Popen([exe, script],
                         creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        try:
            import tkinter as tk
            if tk._default_root:
                tk._default_root.destroy()
        except Exception:
            os._exit(0)

    def _cleanup_git(self):
        """Удалить .git если что-то пошло не так."""
        git_dir = os.path.join(self.app_dir, ".git")
        shutil.rmtree(git_dir, ignore_errors=True)


# ============================================================
# Тестовый запуск
# ============================================================
if __name__ == "__main__":
    REPO_URL = ""
    if not REPO_URL:
        print("Open updater.py and set REPO_URL")
        input("Press Enter...")
        sys.exit(1)

    upd = Updater(repo_url=REPO_URL)
    ok, msg = upd.update()
    print(f"{'OK' if ok else 'ERROR'}: {msg}")
    input("Press Enter...")