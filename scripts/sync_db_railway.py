#!/usr/bin/env python3
"""Загрузка локальной SQLite БД на Railway Volume (замена /data/yaride.db).

Требования:
  - Railway CLI: npm i -g @railway/cli && railway login && railway link
  - Перед загрузкой остановите сервисы yaride-core и yaride_admin (иначе SQLite может повредиться).

Примеры:
  py -3 scripts/sync_db_railway.py
  py -3 scripts/sync_db_railway.py --local yaride.db --volume <volume-id>
  py -3 scripts/sync_db_railway.py --pull   # скачать remote → локально
  py -3 scripts/sync_db_railway.py --mirror-admin   # core volume → admin volume (Railway не шарит volume)
  py -3 scripts/sync_db_railway.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REMOTE = "/data/yaride.db"


def _load_dotenv_db_path() -> Path:
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return ROOT / "yaride.db"
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip() == "DB_PATH":
            raw = value.strip().strip('"').strip("'")
            if raw:
                p = Path(raw)
                return p if p.is_absolute() else (ROOT / p)
    return ROOT / "yaride.db"


def _run(cmd: list[str], *, dry_run: bool = False) -> subprocess.CompletedProcess[str]:
    printable = " ".join(cmd)
    print(f"  $ {printable}")
    if dry_run:
        return subprocess.CompletedProcess(cmd, 0, "", "")
    try:
        return subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=str(ROOT))
    except subprocess.CalledProcessError as exc:
        err = (exc.stderr or exc.stdout or "").strip()
        raise RuntimeError(err or f"команда завершилась с кодом {exc.returncode}") from exc


def _railway_exe() -> str:
    for name in ("railway", "railway.cmd"):
        found = shutil.which(name)
        if found:
            return found
    raise RuntimeError(
        "Railway CLI не найден. Установите: npm i -g @railway/cli, затем railway login && railway link"
    )


def _railway_base() -> list[str]:
    return [_railway_exe()]


def _list_volumes() -> list[dict[str, object]]:
    proc = _run([*_railway_base(), "volume", "list", "--json"])
    data = json.loads(proc.stdout or "[]")
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "volumes" in data:
        inner = data["volumes"]
        return inner if isinstance(inner, list) else []
    return []


def _resolve_volume_id(explicit: str | None) -> str:
    if explicit:
        return explicit.strip()
    volumes = _list_volumes()
    if not volumes:
        raise RuntimeError("Volume не найден. Создайте volume на yaride-core (mount /data) или укажите --volume.")
    if len(volumes) == 1:
        vid = volumes[0].get("id") or volumes[0].get("volumeId")
        name = volumes[0].get("name", "")
        if isinstance(vid, str) and vid:
            print(f"Volume: {name or vid}")
            return vid
    print("Доступные volume:")
    for v in volumes:
        vid = v.get("id") or v.get("volumeId")
        name = v.get("name", "?")
        mount = v.get("mountPath") or v.get("mount_path") or "?"
        print(f"  - {name}  id={vid}  mount={mount}")
    raise RuntimeError("Укажите --volume <id> (несколько volume в проекте).")


def _checkpoint_sqlite(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.commit()
    finally:
        conn.close()
    for suffix in ("-wal", "-shm"):
        sidecar = Path(f"{db_path}{suffix}")
        if sidecar.is_file():
            sidecar.unlink()


def _remote_sidecars(remote_db: str, volume_id: str, *, dry_run: bool) -> None:
    parent = str(Path(remote_db).parent).replace("\\", "/")
    base = Path(remote_db).name
    for suffix in ("-wal", "-shm"):
        remote = f"{parent}/{base}{suffix}"
        try:
            _run(
                [
                    *_railway_base(),
                    "volume",
                    "files",
                    "--volume",
                    volume_id,
                    "delete",
                    remote,
                    "--yes",
                ],
                dry_run=dry_run,
            )
        except RuntimeError:
            pass


def _backup_remote(remote_db: str, volume_id: str, backup_dir: Path, *, dry_run: bool) -> Path | None:
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    local_backup = backup_dir / f"yaride-railway-backup-{stamp}.db"
    try:
        _run(
            [
                *_railway_base(),
                "volume",
                "files",
                "--volume",
                volume_id,
                "download",
                remote_db,
                str(local_backup),
                "--overwrite",
            ],
            dry_run=dry_run,
        )
    except RuntimeError as exc:
        if "not found" in str(exc).lower() or "404" in str(exc):
            print("  (remote БД ещё нет — бэкап пропущен)")
            return None
        raise
    print(f"Бэкап remote: {local_backup}")
    return local_backup


def _volume_id_for_service(service_name: str) -> str:
    volumes = _list_volumes()
    matches = [v for v in volumes if str(v.get("serviceName", "")).lower() == service_name.lower()]
    if len(matches) == 1:
        vid = matches[0].get("id") or matches[0].get("volumeId")
        if isinstance(vid, str) and vid:
            return vid
    if not matches:
        raise RuntimeError(f"Volume для сервиса {service_name!r} не найден.")
    raise RuntimeError(f"Несколько volume для {service_name!r} — укажите --volume вручную.")


def _download_volume_db(volume_id: str, dest: Path, remote_db: str, *, dry_run: bool) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            *_railway_base(),
            "volume",
            "files",
            "--volume",
            volume_id,
            "download",
            remote_db,
            str(dest),
            "--overwrite",
        ],
        dry_run=dry_run,
    )
    if dry_run:
        return
    parent = str(Path(remote_db).parent).replace("\\", "/")
    base = Path(remote_db).name
    for suffix in ("-wal", "-shm"):
        remote = f"{parent}/{base}{suffix}"
        try:
            _run(
                [
                    *_railway_base(),
                    "volume",
                    "files",
                    "--volume",
                    volume_id,
                    "download",
                    remote,
                    str(Path(f"{dest}{suffix}")),
                    "--overwrite",
                ],
                dry_run=False,
            )
        except RuntimeError:
            pass


def mirror_core_to_admin(
    remote_db: str,
    *,
    core_volume: str | None,
    admin_volume: str | None,
    dry_run: bool,
) -> None:
    """Скопировать БД с volume yaride_core на volume yaride_admin.

    Railway не позволяет подключить один volume к двум сервисам — этот режим обходной.
    """
    src_id = core_volume or _volume_id_for_service("yaride_core")
    dst_id = admin_volume or _volume_id_for_service("yaride_admin")
    print(f"Mirror: core volume {src_id} -> admin volume {dst_id}")

    staging = ROOT / "backups" / "mirror-staging.db"
    print("Скачиваем БД с core (включая WAL, если есть)…")
    _download_volume_db(src_id, staging, remote_db, dry_run=dry_run)

    if not dry_run:
        print(f"WAL checkpoint: {staging}")
        _checkpoint_sqlite(staging)

    print("Загружаем на admin volume…")
    push_db(staging, remote_db, dst_id, backup=False, checkpoint=False, dry_run=dry_run)
    print("Готово. Перезапустите yaride_admin: railway redeploy --service yaride_admin -y")


def push_db(
    local_db: Path,
    remote_db: str,
    volume_id: str,
    *,
    backup: bool,
    checkpoint: bool,
    dry_run: bool,
) -> None:
    if not local_db.is_file():
        raise RuntimeError(f"Локальный файл не найден: {local_db}")

    print()
    print("ВАЖНО: остановите в Railway сервисы yaride-core и yaride_admin перед заменой БД.")
    print("       (Deployments -> Stop service или Scale to 0)")
    print()

    if checkpoint:
        print(f"WAL checkpoint: {local_db}")
        if not dry_run:
            _checkpoint_sqlite(local_db)

    if backup:
        print("Скачиваем текущую remote БД…")
        _backup_remote(remote_db, volume_id, ROOT / "backups", dry_run=dry_run)

    print("Удаляем remote WAL/SHM (если есть)…")
    _remote_sidecars(remote_db, volume_id, dry_run=dry_run)

    print(f"Загружаем {local_db} -> {remote_db}")
    _run(
        [
            *_railway_base(),
            "volume",
            "files",
            "--volume",
            volume_id,
            "upload",
            str(local_db),
            remote_db,
            "--overwrite",
        ],
        dry_run=dry_run,
    )
    print("Готово. Запустите yaride-core и yaride_admin снова.")


def pull_db(
    local_db: Path,
    remote_db: str,
    volume_id: str,
    *,
    dry_run: bool,
) -> None:
    if local_db.exists() and not dry_run:
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        backup = local_db.with_name(f"{local_db.stem}.before-pull-{stamp}{local_db.suffix}")
        shutil.copy2(local_db, backup)
        print(f"Локальный бэкап: {backup}")

    _run(
        [
            *_railway_base(),
            "volume",
            "files",
            "--volume",
            volume_id,
            "download",
            remote_db,
            str(local_db),
            "--overwrite",
        ],
        dry_run=dry_run,
    )
    print(f"Скачано: {remote_db} -> {local_db}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Синхронизация yaride.db с Railway Volume")
    parser.add_argument("--local", help="Локальный путь к БД (по умолчанию DB_PATH из .env или yaride.db)")
    parser.add_argument("--remote", default=DEFAULT_REMOTE, help=f"Путь на volume (по умолчанию {DEFAULT_REMOTE})")
    parser.add_argument("--volume", help="ID volume (если не задан — единственный volume в проекте)")
    parser.add_argument("--pull", action="store_true", help="Скачать remote БД на локальную машину")
    parser.add_argument(
        "--mirror-admin",
        action="store_true",
        help="Скопировать БД с volume yaride_core на yaride_admin (обход ограничения Railway)",
    )
    parser.add_argument("--core-volume", help="ID volume yaride_core (для --mirror-admin)")
    parser.add_argument("--admin-volume", help="ID volume yaride_admin (для --mirror-admin)")
    parser.add_argument("--no-backup", action="store_true", help="Не бэкапить remote перед upload")
    parser.add_argument("--no-checkpoint", action="store_true", help="Не делать WAL checkpoint перед upload")
    parser.add_argument("--dry-run", action="store_true", help="Только показать команды")
    args = parser.parse_args(argv)

    local_db = Path(args.local).expanduser().resolve() if args.local else _load_dotenv_db_path()
    remote_db = args.remote.replace("\\", "/")

    try:
        if args.mirror_admin:
            mirror_core_to_admin(
                remote_db,
                core_volume=args.core_volume,
                admin_volume=args.admin_volume,
                dry_run=args.dry_run,
            )
            return 0

        volume_id = _resolve_volume_id(args.volume)
        if args.pull:
            pull_db(local_db, remote_db, volume_id, dry_run=args.dry_run)
        else:
            push_db(
                local_db,
                remote_db,
                volume_id,
                backup=not args.no_backup,
                checkpoint=not args.no_checkpoint,
                dry_run=args.dry_run,
            )
    except RuntimeError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
