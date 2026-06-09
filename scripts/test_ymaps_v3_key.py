"""Probe Yandex Maps JS API v3 key + Referer (no secrets printed)."""
from __future__ import annotations

import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        out[key.strip()] = val.strip().strip('"').strip("'")
    return out


def main() -> None:
    root = load_env(ROOT / ".env")
    mini = load_env(ROOT / "miniapp" / ".env")
    key = (
        mini.get("VITE_YANDEX_MAPS_KEY")
        or root.get("VITE_YANDEX_MAPS_KEY")
        or root.get("YANDEX_GEOCODER_KEY")
        or ""
    ).strip()

    if mini.get("VITE_YANDEX_MAPS_KEY"):
        source = "miniapp/.env VITE_YANDEX_MAPS_KEY"
    elif root.get("VITE_YANDEX_MAPS_KEY"):
        source = "root .env VITE_YANDEX_MAPS_KEY"
    elif root.get("YANDEX_GEOCODER_KEY"):
        source = "root .env YANDEX_GEOCODER_KEY (geocoder fallback — may not support v3!)"
    else:
        source = "MISSING"
    print("key_source:", source)
    print("key_len:", len(key))
    if not key:
        return

    referers = [
        "https://logging-rocks-barbara-promoting.trycloudflare.com/",
        "https://localhost:5174/",
        "https://web.telegram.org/",
        "",  # no referer
    ]
    url = f"https://api-maps.yandex.ru/v3/?apikey={key}&lang=ru_RU"
    for ref in referers:
        label = ref or "(no Referer header)"
        headers = {"User-Agent": "Mozilla/5.0 YarideProbe/1.0"}
        if ref:
            headers["Referer"] = ref
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                body = resp.read(800).decode("utf-8", "replace")
                print(
                    f"referer={label!r} status={resp.status} len={len(body)} "
                    f"ymaps3={'ymaps3' in body} head={body[:100]!r}"
                )
        except urllib.error.HTTPError as err:
            body = err.read(300).decode("utf-8", "replace")
            print(f"referer={label!r} HTTP {err.code} body={body[:150]!r}")
        except Exception as exc:  # noqa: BLE001
            print(f"referer={label!r} ERR {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
