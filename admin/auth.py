"""Аутентификация админов: хэш пароля (pbkdf2_sha256) и проверка по таблице admin_users.

pbkdf2_sha256 выбран намеренно: чистый Python из stdlib hashlib, без внешних бинарных backend'ов
(в отличие от bcrypt), что исключает проблемы совместимости версий на машине оператора.
"""

from __future__ import annotations

from passlib.context import CryptContext

from app.repo import Repo

_pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _pwd_context.verify(password, password_hash)
    except ValueError:
        return False


def authenticate(repo: Repo, username: str, password: str) -> bool:
    """Проверяет логин/пароль и фиксирует время входа. Без раскрытия, что именно неверно — логин или пароль."""
    admin = repo.admin.get_admin(username.strip())
    if not admin:
        return False
    if not verify_password(password, str(admin["password_hash"])):
        return False
    repo.admin.touch_last_login(username.strip())
    return True
