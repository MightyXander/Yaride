"""Запуск веб-админки: py -3 -m admin"""

from __future__ import annotations

import logging

import uvicorn

from admin.app import create_app
from admin.config import load_admin_settings


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = load_admin_settings()
    app = create_app(settings)
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
