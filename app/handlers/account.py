"""Раздел «Аккаунт» и апгрейд пассажира в водителя."""

from __future__ import annotations

import html

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.driver_license import normalize_dl_series_number, parse_expiry_date, validate_license_not_expired
from app.repo import Repo
from app.states import AccountUpgrade

router = Router()


@router.message(F.text == "Аккаунт")
async def account_open(message: Message, repo: Repo) -> None:
    from app.bot_support import account_kb_menu, send_clean_message

    user = repo.users.get_user(message.from_user.id)
    if not user:
        await send_clean_message(message, "Сначала зарегистрируйся через /start.")
        return
    await send_clean_message(
        message,
        "Раздел «Аккаунт»:",
        reply_markup=account_kb_menu(show_become_driver=user["role"] == "passenger"),
    )


@router.callback_query(F.data.startswith("account:"))
async def account_panel(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    from app.bot_support import (
        account_kb_back,
        account_kb_menu,
        edit_or_send_clean,
        flow_keyboard,
        main_keyboard,
        send_clean_message,
    )

    action = callback.data.split(":", 1)[1]
    user = repo.users.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Сначала /start.", show_alert=True)
        return

    show_drv = user["role"] == "passenger"
    menu = account_kb_menu(show_become_driver=show_drv)
    back = account_kb_back()

    if action == "root":
        await edit_or_send_clean(callback, "Раздел «Аккаунт»:", reply_markup=menu)
        await callback.answer()
        return

    if action == "main_menu":
        if callback.message:
            await send_clean_message(
                callback.message,
                "Главное меню",
                reply_markup=main_keyboard(repo, callback.from_user.id),
            )
        await callback.answer()
        return

    if action == "rating":
        rc = int(user["rating_count"] or 0)
        ra = float(user["rating_avg"] or 0.0)
        text = (
            f"Средний рейтинг: {ra:.1f}\nВсего оценок: {rc}" if rc > 0 else "Пока нет оценок от других пользователей."
        )
        await edit_or_send_clean(callback, text, reply_markup=back)
        await callback.answer()
        return

    if action == "reviews":
        rows = repo.ratings.list_ratings_received(callback.from_user.id)
        if not rows:
            txt = "Пока никто не оставил оценок после поездок."
        else:
            lines = []
            for r in rows[:25]:
                line = (
                    f"★ {int(r['stars'])} — от {html.escape(str(r['rater_name']))} | поездка #{r['trip_id']} | "
                    f"{r['trip_date']} {r['departure_time']}"
                )
                rt = r["review_text"]
                if rt:
                    line += f"\n   «{html.escape(str(rt))}»"
                lines.append(line)
            txt = "Оценки после поездок:\n" + "\n".join(lines)
            if len(rows) > 25:
                txt += "\n…"
        await edit_or_send_clean(callback, txt, reply_markup=back)
        await callback.answer()
        return

    if action == "name":
        un = user["username"]
        if un:
            txt = f"Имя в сервисе: {user['name']}\nUsername в Telegram: @{un}"
        else:
            txt = f"Имя в сервисе: {user['name']}\nUsername в Telegram: не указан в профиле Telegram."
        await edit_or_send_clean(callback, txt, reply_markup=back)
        await callback.answer()
        return

    if action == "upgrade_driver":
        if user["role"] != "passenger":
            await callback.answer("Ты уже водитель.", show_alert=True)
            return
        await state.set_state(AccountUpgrade.waiting_dl_series)
        await edit_or_send_clean(
            callback,
            "Стать водителем: проверка формата ВУ (без запросов в ГИБДД).\n\n"
            "Введи серию и номер как на пластиковом бланке: 4 цифры, 2 буквы "
            "(А, В, Е, К, М, Н, О, Р, С, Т, У, Х), 6 цифр. Можно с пробелами — например 9916 АВ 123456.",
            reply_markup=flow_keyboard(),
        )
        await callback.answer()
        return

    await callback.answer()


@router.message(AccountUpgrade.waiting_dl_series)
async def account_upgrade_dl_series(message: Message, state: FSMContext) -> None:
    from app.bot_support import flow_keyboard, send_clean_message

    ok, normalized, err = normalize_dl_series_number(message.text or "")
    if not ok:
        await send_clean_message(message, err or "Некорректные данные ВУ.")
        return
    await state.update_data(dl_series_number=normalized)
    await state.set_state(AccountUpgrade.waiting_dl_expiry)
    await send_clean_message(
        message,
        "Введи дату окончания срока действия ВУ (поле «3b») в формате ДД.ММ.ГГГГ.",
        reply_markup=flow_keyboard(),
    )


@router.message(AccountUpgrade.waiting_dl_expiry)
async def account_upgrade_dl_expiry(message: Message, state: FSMContext, repo: Repo) -> None:
    from app.bot_support import main_keyboard, send_clean_message

    ok, expiry_date, err = parse_expiry_date(message.text or "")
    if not ok or not expiry_date:
        await send_clean_message(message, err or "Некорректная дата.")
        return
    ok_exp, msg_exp = validate_license_not_expired(expiry_date)
    if not ok_exp:
        await send_clean_message(message, msg_exp or "ВУ недействительно.")
        return
    user = repo.users.get_user(message.from_user.id)
    if not user or user["role"] != "passenger":
        await send_clean_message(message, "Сессия устарела или роль уже изменена.")
        await state.clear()
        return
    data = await state.get_data()
    dl_series = data.get("dl_series_number")
    if not dl_series:
        await send_clean_message(message, "Сначала введи серию и номер ВУ.")
        await state.set_state(AccountUpgrade.waiting_dl_series)
        return
    try:
        repo.users.upsert_user(
            message.from_user.id,
            str(user["name"]),
            message.from_user.username,
            "driver",
            dl_series_number=str(dl_series),
            dl_valid_until=expiry_date.isoformat(),
        )
    except ValueError as exc:
        await send_clean_message(message, str(exc))
        return
    await state.clear()
    await send_clean_message(
        message,
        "Ты зарегистрирован как водитель. Формат ВУ проверен локально.\n"
        "В меню доступны создание поездок и раздел «Управление».",
        reply_markup=main_keyboard(repo, message.from_user.id),
    )


@router.message(F.text == "⬅ Назад", StateFilter(AccountUpgrade.waiting_dl_expiry))
async def account_upgrade_back_from_expiry(message: Message, state: FSMContext) -> None:
    from app.bot_support import flow_keyboard, send_clean_message

    await state.set_state(AccountUpgrade.waiting_dl_series)
    await send_clean_message(
        message,
        "Введи серию и номер ВУ как на пластиковом бланке.",
        reply_markup=flow_keyboard(),
    )


@router.message(F.text == "⬅ Назад", StateFilter(AccountUpgrade.waiting_dl_series))
async def account_upgrade_back_from_series(message: Message, state: FSMContext, repo: Repo) -> None:
    from app.bot_support import account_kb_menu, send_clean_message

    await state.clear()
    user = repo.users.get_user(message.from_user.id)
    if not user:
        await send_clean_message(message, "Сначала зарегистрируйся через /start.")
        return
    await send_clean_message(
        message,
        "Раздел «Аккаунт»:",
        reply_markup=account_kb_menu(show_become_driver=user["role"] == "passenger"),
    )
