"""Регистрация: /start, имя, роль, ВУ."""

from __future__ import annotations

import html

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.driver_license import normalize_dl_series_number, parse_expiry_date, validate_license_not_expired
from app.repo import Repo
from app.states import Registration

router = Router()


@router.message(Command("start"))
async def start(message: Message, state: FSMContext, repo: Repo) -> None:
    from app.bot_support import cleanup_chat, drop_empty_chat_bridge, role_keyboard, track_bot_message

    bridge_id = await cleanup_chat(message)
    await state.clear()
    user = repo.users.get_user(message.from_user.id)
    if user:
        name = str(user["name"] or "").strip() or (message.from_user.first_name or "друг")
        await state.update_data(name=name)
        await state.set_state(Registration.waiting_role)
        text = f"<b>{html.escape(name)}</b> Давно не виделись. Выберите вашу роль:"
        sent = await message.answer(text, parse_mode="HTML", reply_markup=role_keyboard())
        await track_bot_message(sent)
        await drop_empty_chat_bridge(message, bridge_id)
        return
    await state.set_state(Registration.waiting_name)
    sent = await message.answer("Привет! Введи имя пользователя — так тебя будут видеть другие участники.")
    await track_bot_message(sent)
    await drop_empty_chat_bridge(message, bridge_id)


@router.message(Registration.waiting_name)
async def reg_name(message: Message, state: FSMContext) -> None:
    from app.bot_support import role_keyboard, send_clean_message

    name = (message.text or "").strip()
    if len(name) < 2:
        await send_clean_message(message, "Имя пользователя слишком короткое, попробуй ещё раз.")
        return
    await state.update_data(name=name)
    await state.set_state(Registration.waiting_role)
    await send_clean_message(message, "Выбери роль:", reply_markup=role_keyboard())


@router.callback_query(F.data.startswith("set_role:"))
async def reg_role(callback: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    from app.bot_support import edit_or_send_clean, flow_keyboard, main_keyboard

    role = callback.data.split(":", 1)[1]
    data = await state.get_data()
    name = data.get("name")
    if not name:
        await edit_or_send_clean(callback, "Сессия регистрации устарела. Нажми /start.")
        await state.clear()
        await callback.answer()
        return
    if role == "passenger":
        repo.users.upsert_user(callback.from_user.id, str(name), callback.from_user.username, "passenger")
        await state.clear()
        await edit_or_send_clean(
            callback,
            "Профиль сохранён.\nУсловия сервиса: плата покрывает бензин и износ, сервис не является такси.",
            reply_markup=main_keyboard(repo, callback.from_user.id),
        )
        await callback.answer("Роль сохранена")
        return
    if role == "driver":
        await state.set_state(Registration.waiting_dl_series)
        await edit_or_send_clean(
            callback,
            "Роль «водитель»: сначала локальная проверка формата ВУ (без запросов в ГИБДД).\n\n"
            "Введи серию и номер как на пластиковом бланке: 4 цифры, 2 буквы "
            "(А, В, Е, К, М, Н, О, Р, С, Т, У, Х), 6 цифр. Можно с пробелами — например 9916 АВ 123456.",
            reply_markup=flow_keyboard(),
        )
        await callback.answer()
        return
    await callback.answer("Неизвестная роль.", show_alert=True)


@router.message(Registration.waiting_dl_series)
async def reg_dl_series(message: Message, state: FSMContext) -> None:
    from app.bot_support import flow_keyboard, send_clean_message

    ok, normalized, err = normalize_dl_series_number(message.text or "")
    if not ok:
        await send_clean_message(message, err or "Некорректные данные ВУ.")
        return
    await state.update_data(dl_series_number=normalized)
    await state.set_state(Registration.waiting_dl_expiry)
    await send_clean_message(
        message,
        "Теперь введи дату окончания срока действия ВУ (поле «3b») в формате ДД.ММ.ГГГГ.",
        reply_markup=flow_keyboard(),
    )


@router.message(Registration.waiting_dl_expiry)
async def reg_dl_expiry(message: Message, state: FSMContext, repo: Repo) -> None:
    from app.bot_support import main_keyboard, send_clean_message

    ok, expiry_date, err = parse_expiry_date(message.text or "")
    if not ok or not expiry_date:
        await send_clean_message(message, err or "Некорректная дата.")
        return
    ok_exp, msg_exp = validate_license_not_expired(expiry_date)
    if not ok_exp:
        await send_clean_message(message, msg_exp or "ВУ недействительно.")
        return
    data = await state.get_data()
    name = data.get("name")
    if not name:
        await send_clean_message(message, "Сессия регистрации устарела. Нажми /start.")
        await state.clear()
        return
    dl_series = data.get("dl_series_number")
    if not dl_series:
        await send_clean_message(message, "Сначала введи серию и номер ВУ.")
        await state.set_state(Registration.waiting_dl_series)
        return
    try:
        repo.users.upsert_user(
            message.from_user.id,
            str(name),
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
        "Профиль водителя сохранён: формат ВУ проверен локально.\n"
        "Условия сервиса: плата покрывает бензин и износ, сервис не является такси.",
        reply_markup=main_keyboard(repo, message.from_user.id),
    )
