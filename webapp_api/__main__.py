"""Запуск Mini App API: py -3 -m webapp_api."""

from __future__ import annotations

import uvicorn

from webapp_api.app import create_app
from webapp_api.config import load_webapp_settings


def main() -> None:
    settings = load_webapp_settings()
    app = create_app(settings)
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
