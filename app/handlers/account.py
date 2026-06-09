"""Раздел «Аккаунт» и апгрейд пассажира в водителя."""

from __future__ import annotations

import html

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.chat_ui import ChatUiService
from app.driver_license import normalize_dl_series_number, parse_expiry_date, validate_license_not_expired
from app.driver_access import is_approved_driver, is_pending_driver
from app.repo import Repo
from app.states import AccountUpgrade
from app.ui import KeyboardFactory

router = Router()

FLOW_KIND = "account"


def _account_root_markup(user_row, keyboards: KeyboardFactory):
    return keyboards.with_back_button(
        keyboards.account_menu_keyboard(show_become_driver=user_row["role"] == "passenger"),
        target="menu",
    )


def _mk(repo: Repo, keyboards: KeyboardFactory, tg_user_id: int):
    u = repo.users.get_user(tg_user_id)
    return keyboards.main_keyboard(is_driver=repo.users.is_active_driver(tg_user_id))


@router.message(F.text == "Аккаунт")
async def account_open(
    message: Message,
    repo: Repo,
    chat_ui: ChatUiService,
    keyboards: KeyboardFactory,
) -> None:
    user = repo.users.get_user(message.from_user.id)
    await chat_ui.delete_user_message(message)
    if not user:
        await chat_ui.close_flow(chat_id=message.chat.id, bot=message.bot)
        await chat_ui.replace_with_notice(
            chat_id=message.chat.id,
            bot=message.bot,
            text="Сначала зарегистрируйся через /start.",
            reply_keyboard=_mk(repo, keyboards, message.from_user.id),
        )
        return
    await chat_ui.open_flow(
        chat_id=message.chat.id,
        bot=message.bot,
        flow_kind=FLOW_KIND,
        text="Раздел «Аккаунт»:",
        inline_markup=_account_root_markup(user, keyboards),
    )


@router.callback_query(F.data.startswith("account:"))
async def account_panel(
    callback: CallbackQuery,
    state: FSMContext,
    repo: Repo,
    chat_ui: ChatUiService,
    keyboards: KeyboardFactory,
) -> None:
    action = callback.data.split(":", 1)[1]
    user = repo.users.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Сначала /start.", show_alert=True)
        return
    if not callback.message:
        await callback.answer()
        return

    chat_id = callback.message.chat.id
    bot = callback.bot
    back = keyboards.account_back_keyboard()

    if action == "root":
        await chat_ui.update_flow(
            chat_id=chat_id,
            bot=bot,
            flow_kind=FLOW_KIND,
            text="Раздел «Аккаунт»:",
            inline_markup=_account_root_markup(user, keyboards),
        )
        await callback.answer()
        return

    if action == "main_menu":
        # Совместимость: старые anchor могут содержать кнопку «⬅ Главное меню».
        await chat_ui.close_flow(chat_id=chat_id, bot=bot)
        await chat_ui.replace_with_notice(
            chat_id=chat_id,
            bot=bot,
            text="Главное меню",
            reply_keyboard=_mk(repo, keyboards, callback.from_user.id),
        )
        await callback.answer()
        return

    if action == "rating":
        rc = int(user["rating_count"] or 0)
        ra = float(user["rating_avg"] or 0.0)
        text = (
            f"Средний рейтинг: {ra:.1f}\nВсего оценок: {rc}" if rc > 0 else "Пока нет оценок от других пользователей."
        )
        await chat_ui.update_flow(chat_id=chat_id, bot=bot, flow_kind=FLOW_KIND, text=text, inline_markup=back)
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
        await chat_ui.update_flow(chat_id=chat_id, bot=bot, flow_kind=FLOW_KIND, text=txt, inline_markup=back)
        await callback.answer()
        return

    if action == "name":
        un = user["username"]
        if un:
            txt = f"Имя в сервисе: {user['name']}\nUsername в Telegram: @{un}"
        else:
            txt = f"Имя в сервисе: {user['name']}\nUsername в Telegram: не указан в профиле Telegram."
        await chat_ui.update_flow(chat_id=chat_id, bot=bot, flow_kind=FLOW_KIND, text=txt, inline_markup=back)
        await callback.answer()
        return

    if action == "upgrade_driver":
        if is_approved_driver(user):
            await callback.answer("Ты уже водитель.", show_alert=True)
            return
        if is_pending_driver(user):
            await callback.answer("Заявка водителя уже на модерации.", show_alert=True)
            return
        await state.set_state(AccountUpgrade.waiting_dl_series)
        await chat_ui.update_flow(
            chat_id=chat_id,
            bot=bot,
            flow_kind=FLOW_KIND,
            text=(
                "Стать водителем: проверка формата ВУ (без запросов в ГИБДД).\n\n"
                "Введи серию и номер как на пластиковом бланке: 4 цифры, 2 буквы "
                "(А, В, Е, К, М, Н, О, Р, С, Т, У, Х), 6 цифр. Можно с пробелами — например 9916 АВ 123456."
            ),
            inline_markup=None,
            reply_keyboard=keyboards.flow_keyboard(),
        )
        await callback.answer()
        return

    await callback.answer()


@router.message(AccountUpgrade.waiting_dl_series)
async def account_upgrade_dl_series(
    message: Message,
    state: FSMContext,
    chat_ui: ChatUiService,
    keyboards: KeyboardFactory,
) -> None:
    ok, normalized, err = normalize_dl_series_number(message.text or "")
    await chat_ui.delete_user_message(message)
    if not ok:
        await chat_ui.update_flow(
            chat_id=message.chat.id,
            bot=message.bot,
            flow_kind=FLOW_KIND,
            text=err or "Некорректные данные ВУ.",
            reply_keyboard=keyboards.flow_keyboard(),
        )
        return
    await state.update_data(dl_series_number=normalized)
    await state.set_state(AccountUpgrade.waiting_dl_expiry)
    await chat_ui.update_flow(
        chat_id=message.chat.id,
        bot=message.bot,
        flow_kind=FLOW_KIND,
        text="Введи дату окончания срока действия ВУ (поле «3b») в формате ДД.ММ.ГГГГ.",
        reply_keyboard=keyboards.flow_keyboard(),
    )


@router.message(AccountUpgrade.waiting_dl_expiry)
async def account_upgrade_dl_expiry(
    message: Message,
    state: FSMContext,
    repo: Repo,
    chat_ui: ChatUiService,
    keyboards: KeyboardFactory,
) -> None:
    raw = message.text or ""
    await chat_ui.delete_user_message(message)
    ok, expiry_date, err = parse_expiry_date(raw)
    if not ok or not expiry_date:
        await chat_ui.update_flow(
            chat_id=message.chat.id,
            bot=message.bot,
            flow_kind=FLOW_KIND,
            text=err or "Некорректная дата.",
            reply_keyboard=keyboards.flow_keyboard(),
        )
        return
    ok_exp, msg_exp = validate_license_not_expired(expiry_date)
    if not ok_exp:
        await chat_ui.update_flow(
            chat_id=message.chat.id,
            bot=message.bot,
            flow_kind=FLOW_KIND,
            text=msg_exp or "ВУ недействительно.",
            reply_keyboard=keyboards.flow_keyboard(),
        )
        return
    user = repo.users.get_user(message.from_user.id)
    if not user or user["role"] != "passenger":
        await state.clear()
        await chat_ui.close_flow(chat_id=message.chat.id, bot=message.bot)
        await chat_ui.replace_with_notice(
            chat_id=message.chat.id,
            bot=message.bot,
            text="Сессия устарела или роль уже изменена.",
            reply_keyboard=_mk(repo, keyboards, message.from_user.id),
        )
        return
    data = await state.get_data()
    dl_series = data.get("dl_series_number")
    if not dl_series:
        await state.set_state(AccountUpgrade.waiting_dl_series)
        await chat_ui.update_flow(
            chat_id=message.chat.id,
            bot=message.bot,
            flow_kind=FLOW_KIND,
            text="Сначала введи серию и номер ВУ.",
            reply_keyboard=keyboards.flow_keyboard(),
        )
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
        await chat_ui.update_flow(
            chat_id=message.chat.id,
            bot=message.bot,
            flow_kind=FLOW_KIND,
            text=str(exc),
            reply_keyboard=keyboards.flow_keyboard(),
        )
        return
    await state.clear()
    await chat_ui.close_flow(chat_id=message.chat.id, bot=message.bot)
    await chat_ui.replace_with_notice(
        chat_id=message.chat.id,
        bot=message.bot,
        text=(
            "Заявка водителя отправлена на модерацию.\n"
            "После одобрения администратором откроются создание поездок и раздел «Управление»."
        ),
        reply_keyboard=_mk(repo, keyboards, message.from_user.id),
    )


@router.message(F.text == "⬅ Назад", StateFilter(AccountUpgrade.waiting_dl_expiry))
async def account_upgrade_back_from_expiry(
    message: Message,
    state: FSMContext,
    chat_ui: ChatUiService,
    keyboards: KeyboardFactory,
) -> None:
    await chat_ui.delete_user_message(message)
    await state.set_state(AccountUpgrade.waiting_dl_series)
    await chat_ui.update_flow(
        chat_id=message.chat.id,
        bot=message.bot,
        flow_kind=FLOW_KIND,
        text="Введи серию и номер ВУ как на пластиковом бланке.",
        reply_keyboard=keyboards.flow_keyboard(),
    )


@router.message(F.text == "⬅ Назад", StateFilter(AccountUpgrade.waiting_dl_series))
async def account_upgrade_back_from_series(
    message: Message,
    state: FSMContext,
    repo: Repo,
    chat_ui: ChatUiService,
    keyboards: KeyboardFactory,
) -> None:
    await state.clear()
    await chat_ui.delete_user_message(message)
    user = repo.users.get_user(message.from_user.id)
    if not user:
        await chat_ui.close_flow(chat_id=message.chat.id, bot=message.bot)
        await chat_ui.replace_with_notice(
            chat_id=message.chat.id,
            bot=message.bot,
            text="Сначала зарегистрируйся через /start.",
            reply_keyboard=_mk(repo, keyboards, message.from_user.id),
        )
        return
    await chat_ui.update_flow(
        chat_id=message.chat.id,
        bot=message.bot,
        flow_kind=FLOW_KIND,
        text="Раздел «Аккаунт»:",
        inline_markup=_account_root_markup(user, keyboards),
        reply_keyboard=None,
    )
