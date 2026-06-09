"""
Принудительно пересчитывает координаты остановок в БД из каталога.

После обновления app/stop_coordinates.json штатный bootstrap заполняет координаты
только там, где они NULL. Этот скрипт переписывает координаты у ВСЕХ остановок
по приоритету override → каталог → центр района (см. app.geo_stops.lat_lng_for_stop),
чтобы применить новый геокод к уже существующей базе.

Запуск из корня репозитория (можно при запущенном бэкенде — он читает координаты из БД на лету):
  py -3 scripts/resync_stop_coordinates.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

from app.db import Database  # noqa: E402
from app.geo_stops import lat_lng_for_stop  # noqa: E402


def main() -> None:
    load_dotenv()
    db_path = (os.getenv("DB_PATH") or "yaride.db").strip() or "yaride.db"
    db = Database(db_path)
    try:
        with db.transaction() as conn:
            rows = conn.execute(
                "SELECT id, locality, district, admin_area, title FROM route_points WHERE kind = 'stop'"
            ).fetchall()
            updated = 0
            for r in rows:
                lat, lng = lat_lng_for_stop(
                    str(r["locality"]),
                    str(r["district"] or ""),
                    str(r["admin_area"] or ""),
                    str(r["title"]),
                )
                conn.execute(
                    "UPDATE route_points SET latitude = ?, longitude = ? WHERE id = ?",
                    (lat, lng, int(r["id"])),
                )
                updated += 1
        print(f"Обновлено координат: {updated} (БД: {db_path})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
