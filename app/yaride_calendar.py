"""Виджет календаря aiogram-calendar с русскими подсказками и скрытием прошедших дат."""

from __future__ import annotations

import calendar
from datetime import datetime

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram_calendar import SimpleCalendar, SimpleCalendarCallback
from aiogram_calendar.schemas import SimpleCalAct


class YarideCalendar(SimpleCalendar):
    """Календарь с русскими подсказками при выходе за допустимый диапазон дат."""

    async def start_calendar(
        self,
        year: int = datetime.now().year,
        month: int = datetime.now().month,
    ) -> InlineKeyboardMarkup:
        """Календарь, где прошедшие даты скрыты (пустые ячейки)."""
        today = datetime.now()
        now_weekday = self._labels.days_of_week[today.weekday()]
        now_month, now_year, now_day = today.month, today.year, today.day

        def is_out_of_range(day_num: int) -> bool:
            date_to_check = datetime(year, month, day_num)
            if self.min_date and date_to_check < self.min_date:
                return True
            if self.max_date and date_to_check > self.max_date:
                return True
            return False

        def highlight_month() -> str:
            month_str = self._labels.months[month - 1]
            if now_month == month and now_year == year:
                return f"[{month_str}]"
            return month_str

        def weekday_label(weekday: str) -> str:
            if now_month == month and now_year == year and now_weekday == weekday:
                return f"[{weekday}]"
            return weekday

        kb: list[list[InlineKeyboardButton]] = []

        years_row = [
            InlineKeyboardButton(
                text="<<",
                callback_data=SimpleCalendarCallback(act=SimpleCalAct.prev_y, year=year, month=month, day=1).pack(),
            ),
            InlineKeyboardButton(
                text=str(year) if year != now_year else f"[{year}]",
                callback_data=self.ignore_callback,
            ),
            InlineKeyboardButton(
                text=">>",
                callback_data=SimpleCalendarCallback(act=SimpleCalAct.next_y, year=year, month=month, day=1).pack(),
            ),
        ]
        kb.append(years_row)

        month_row = [
            InlineKeyboardButton(
                text="<",
                callback_data=SimpleCalendarCallback(act=SimpleCalAct.prev_m, year=year, month=month, day=1).pack(),
            ),
            InlineKeyboardButton(
                text=highlight_month(),
                callback_data=self.ignore_callback,
            ),
            InlineKeyboardButton(
                text=">",
                callback_data=SimpleCalendarCallback(act=SimpleCalAct.next_m, year=year, month=month, day=1).pack(),
            ),
        ]
        kb.append(month_row)

        week_days_labels_row: list[InlineKeyboardButton] = []
        for weekday in self._labels.days_of_week:
            week_days_labels_row.append(
                InlineKeyboardButton(text=weekday_label(weekday), callback_data=self.ignore_callback)
            )
        kb.append(week_days_labels_row)

        month_calendar = calendar.monthcalendar(year, month)
        for week in month_calendar:
            days_row: list[InlineKeyboardButton] = []
            for day in week:
                if day == 0:
                    days_row.append(InlineKeyboardButton(text=" ", callback_data=self.ignore_callback))
                    continue
                if is_out_of_range(day):
                    days_row.append(InlineKeyboardButton(text=" ", callback_data=self.ignore_callback))
                    continue

                day_text = str(day)
                if now_month == month and now_year == year and now_day == day:
                    day_text = f"[{day_text}]"
                days_row.append(
                    InlineKeyboardButton(
                        text=day_text,
                        callback_data=SimpleCalendarCallback(
                            act=SimpleCalAct.day, year=year, month=month, day=day
                        ).pack(),
                    )
                )
            kb.append(days_row)

        cancel_row = [
            InlineKeyboardButton(
                text=self._labels.cancel_caption,
                callback_data=SimpleCalendarCallback(act=SimpleCalAct.cancel, year=year, month=month, day=1).pack(),
            ),
            InlineKeyboardButton(text=" ", callback_data=self.ignore_callback),
            InlineKeyboardButton(
                text=self._labels.today_caption,
                callback_data=SimpleCalendarCallback(act=SimpleCalAct.today, year=year, month=month, day=1).pack(),
            ),
        ]
        kb.append(cancel_row)
        return InlineKeyboardMarkup(row_width=7, inline_keyboard=kb)

    async def process_selection(self, query, data: SimpleCalendarCallback) -> tuple:
        if data.act == SimpleCalAct.today:
            now = datetime.now()
            day_data = SimpleCalendarCallback(
                act=SimpleCalAct.day,
                year=now.year,
                month=now.month,
                day=now.day,
            )
            return await self.process_day_select(day_data, query)
        return await super().process_selection(query, data)

    async def process_day_select(self, data, query):
        picked = datetime(int(data.year), int(data.month), int(data.day))
        if self.min_date and self.min_date > picked:
            await query.answer(
                f"Нельзя выбрать прошедшую дату. Доступно с {self.min_date.strftime('%d.%m.%Y')}.",
                show_alert=self.show_alerts,
            )
            return False, None
        if self.max_date and self.max_date < picked:
            await query.answer(
                f"Выберите дату не позже {self.max_date.strftime('%d.%m.%Y')}.",
                show_alert=self.show_alerts,
            )
            return False, None
        await query.message.delete_reply_markup()
        return True, picked


def trip_calendar() -> YarideCalendar:
    """Календарь без прошедших дат (с сегодняшнего дня)."""
    cal = YarideCalendar(
        locale="ru_RU",
        show_alerts=True,
        cancel_btn="Отмена",
        today_btn="Сегодня",
    )
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    cal.set_dates_range(today_start, None)
    return cal
