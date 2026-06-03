"""CLI управления админами: создание учётной записи и смена пароля.

Запуск:
    py -3 -m admin.cli create-admin <логин>
    py -3 -m admin.cli set-password <логин>
Пароль запрашивается интерактивно (не передаётся аргументом, чтобы не попасть в историю shell).
"""

from __future__ import annotations

import getpass
import sys

from admin.auth import hash_password
from admin.config import load_admin_settings
from app.db import Database
from app.repo import Repo


def _repo() -> Repo:
    settings = load_admin_settings()
    db = Database(settings.db_path)
    db.init_schema()
    return Repo(db)


def _read_password() -> str:
    pwd = getpass.getpass("Пароль: ")
    if len(pwd) < 8:
        raise SystemExit("Пароль слишком короткий (минимум 8 символов).")
    if pwd != getpass.getpass("Повтор пароля: "):
        raise SystemExit("Пароли не совпадают.")
    return pwd


def create_admin(username: str) -> None:
    repo = _repo()
    pwd = _read_password()
    repo.admin.create_admin(username, hash_password(pwd))
    print(f"Администратор '{username}' создан.")


def set_password(username: str) -> None:
    repo = _repo()
    if repo.admin.get_admin(username) is None:
        raise SystemExit(f"Администратор '{username}' не найден.")
    pwd = _read_password()
    repo.admin.set_password_hash(username, hash_password(pwd))
    print(f"Пароль администратора '{username}' обновлён.")


def main(argv: list[str]) -> None:
    if len(argv) != 2:
        raise SystemExit("Использование: py -3 -m admin.cli {create-admin|set-password} <логин>")
    command, username = argv
    if command == "create-admin":
        create_admin(username)
    elif command == "set-password":
        set_password(username)
    else:
        raise SystemExit(f"Неизвестная команда: {command}")


if __name__ == "__main__":
    main(sys.argv[1:])
