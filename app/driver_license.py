"""Форматная проверка российского ВУ без обращения к ГИБДД."""

from __future__ import annotations

from datetime import date, datetime

# Буквы серии/номера как на регистрационных знаках РФ (используются на бланке ВУ).
_DL_LETTERS = frozenset("АВЕКМНОРСТУХ")

_LATIN_TO_RU = {
    "A": "А",
    "B": "В",
    "E": "Е",
    "K": "К",
    "M": "М",
    "H": "Н",
    "O": "О",
    "P": "Р",
    "C": "С",
    "T": "Т",
    "Y": "У",
    "X": "Х",
}


def _normalize_series_letter(ch: str) -> str | None:
    if ch in _DL_LETTERS:
        return ch
    if len(ch) == 1 and ch.upper() in _LATIN_TO_RU:
        return _LATIN_TO_RU[ch.upper()]
    return None


def normalize_dl_series_number(raw: str) -> tuple[bool, str | None, str | None]:
    """
    Проверяет серию и номер ВУ РФ: 4 цифры + 2 буквы + 6 цифр (всего 12 символов).

    Допускаются пробелы и дефисы; латинские «похожие» буквы приводятся к русским.

    Возвращает (успех, нормализованная строка из 12 символов или None, текст ошибки).
    """
    if not raw or not str(raw).strip():
        return False, None, "Введите серию и номер водительского удостоверения."

    compact: list[str] = []
    for ch in str(raw).strip():
        if ch.isspace() or ch in "-–—":
            continue
        if ch.isdigit():
            compact.append(ch)
            continue
        if ch.isalpha():
            uch = ch.upper()
            ru = _normalize_series_letter(uch)
            if ru:
                compact.append(ru)
                continue
            return (
                False,
                None,
                "Допустимы только цифры и буквы А, В, Е, К, М, Н, О, Р, С, Т, У, Х "
                "(русские или похожие латинские).",
            )
        return False, None, "Уберите лишние символы из серии и номера ВУ."

    s = "".join(compact)
    if len(s) != 12:
        return (
            False,
            None,
            "Серия и номер ВУ: нужно ровно 12 символов без разделителей — "
            "4 цифры серии, 2 буквы серии, 6 цифр номера (пример: 9916АВ123456).",
        )

    if not all(c.isdigit() for c in s[:4]):
        return False, None, "Первые четыре символа серии ВУ должны быть цифрами."

    if s[4] not in _DL_LETTERS or s[5] not in _DL_LETTERS:
        return False, None, "После четырёх цифр должны следовать две буквы серии (как на бланке ВУ)."

    if not all(c.isdigit() for c in s[6:12]):
        return False, None, "Последние шесть символов — номер ВУ, только цифры."

    return True, s, None


def parse_expiry_date(raw: str) -> tuple[bool, date | None, str | None]:
    """Разбирает дату окончания срока действия ВУ (ДД.ММ.ГГГГ и близкие варианты)."""
    raw_clean = (raw or "").strip()
    if not raw_clean:
        return False, None, "Укажите дату окончания срока действия ВУ."

    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return True, datetime.strptime(raw_clean, fmt).date(), None
        except ValueError:
            continue

    return False, None, "Дата окончания срока действия: формат ДД.ММ.ГГГГ (например 31.12.2030)."


def validate_license_not_expired(valid_until: date, today: date | None = None) -> tuple[bool, str | None]:
    """Проверяет, что срок действия ВУ не истёк (локальная дата «сегодня»)."""
    ref = today if today is not None else date.today()
    if valid_until < ref:
        return False, "Срок действия ВУ уже истёк. Нужно действующее удостоверение."
    return True, None
