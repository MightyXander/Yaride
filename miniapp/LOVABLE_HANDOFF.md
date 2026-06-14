# Yaride Mini App — передача в Lovable (UI/UX)

Полный фронт Telegram Mini App. **Задача для Lovable:** вёрстка, анимации, микро-интеракции, полировка mobile UX. **Не ломать** API, роутинг, карты, auth.

## Стек (не менять)

- TanStack Start + React 19 + Vite 7 + Nitro (`node-server`)
- Tailwind CSS v4 (`src/styles.css` — design tokens)
- TanStack Query → `src/lib/api.ts` (`X-Init-Data`)
- Framer Motion — `src/components/page-transition.tsx`
- Telegram WebApp — `src/lib/telegram.tsx`
- Шрифт: Manrope (Google Fonts в `__root.tsx`)

## Дизайн

- Референс: T-Bank / fintech dark + жёлтый бренд `#ffdd2d`
- Референс-скрины (если есть в репо): `_design_ref/stitch_remix_of_buro_fintech_app/`
- Токены: `src/styles.css` (`--brand`, `.brand-gradient`, `.surface-elevated`, `.tg-section`, `.press`, `.stagger-in`)
- UI-kit: `src/components/ui-kit.tsx` — **единая точка** для Screen, BottomCTA, Card, TextInput, TripCard и т.д.

## Экраны (file routes `src/routes/`)

| Файл | Путь | Что на экране |
|------|------|----------------|
| `index.tsx` | `/` | Редирект / gate |
| `onboarding.tsx` | `/onboarding` | 3 шага: имя → роль → ВУ/авто |
| `home.tsx` | `/home` | Главная, меню, CTA водителя |
| `search.tsx` | `/search` | Поиск поездок, фильтры |
| `create.tsx` | `/create` | Мастер создания поездки |
| `route.map.tsx` | `/route/map` | Выбор точки на карте |
| `trip.$id.tsx` | `/trip/$id` | Детали поездки |
| `bookings.tsx` | `/bookings` | Мои брони |
| `manage.tsx` | `/manage` | Поездки водителя |
| `account.tsx` | `/account` | Профиль |
| `license.tsx` | `/license` | Редактирование ВУ |
| `favorites.tsx` | `/favorites` | Избранные маршруты |
| `history.tsx` | `/history` | История |
| `notifications.tsx` | `/notifications` | Уведомления |
| `rate.$id.tsx` | `/rate/$id` | Оценка после поездки |

## Ключевые компоненты (`src/components/`)

| Файл | Назначение |
|------|------------|
| `ui-kit.tsx` | Design system: Screen, BottomCTA, Card, Field, TextInput, Chip, TripCard… |
| `floating-nav.tsx` | Pill-навигация снизу (не BottomNav Telegram) |
| `page-transition.tsx` | Анимации переходов между экранами |
| `stop-map-picker.tsx` | Карта выбора остановки (v3 + legacy fallback) |
| `stop-map-legacy.tsx` | Яндекс Maps 2.1 fallback |
| `route-pick-steps.tsx` | Шаги выбора маршрута |
| `yandex-route-card.tsx` | Карточка маршрута |
| `search-filter-sheet.tsx` | Bottom sheet фильтров |
| `booked-success-sheet.tsx` | Успешная бронь |
| `crown-time-picker.tsx` | Выбор времени |

## Что просим поправить (приоритет)

1. **Анимации** — page transitions, stagger lists, sheet enter/exit, micro-interactions на кнопках/карточках
2. **Вёрстка форм** — онбординг, license, create: отступы, клавиатура, поля не перекрываются CTA/nav
3. **Bottom CTA** — жёлтая кнопка вместо Telegram MainButton (`BottomCTA forceInPage`), согласованность отступов с `floating-nav`
4. **Карта** — layout ошибки/лоадера, bottom sheet поверх карты, поиск остановок
5. **Типографика и ритм** — заголовки ScreenHeader, секции, пустые состояния EmptyState
6. **Dark theme** — полировка контраста, elevated surfaces, карточки поездок
7. **Safe area** — iPhone notch, Telegram viewport, `env(safe-area-inset-*)`

## Не трогать без согласования

- `src/lib/api.ts`, `queries.ts`, `init-data.ts` — контракт с бэкендом
- `src/lib/license-validation.ts` — зеркало Python-валидации ВУ
- `src/lib/ymaps3*.ts`, `stop-map-legacy.tsx` — Яндекс.Карты
- `server/routes/` — прокси API и ymaps на Railway
- `vite.config.ts` nitro preset, `routeTree.gen.ts` (генерируется)
- Логику `useMainButton` — везде in-page `BottomCTA forceInPage`

## Локальный запуск

```bash
# из корня Yaride
py -3 scripts/dev.py
# или только фронт:
cd miniapp && npm install && npm run dev
# :5174, прокси /api → :8080
```

Dev без Telegram: `WEBAPP_DEV_USER_ID` в корневом `.env`.

## Промпт для Lovable (скопировать)

```
Проект: Yaride — Telegram Mini App карпулинга (Ярославль).
Стек: TanStack Start, React 19, Tailwind v4, Framer Motion.

Задача: полировка UI/UX — анимации переходов, stagger-списки, bottom sheets,
формы (клавиатура + safe area), жёлтый бренд #ffdd2d на тёмном фоне.

Читай LOVABLE_HANDOFF.md и src/styles.css. Переиспользуй ui-kit.tsx и floating-nav.tsx.
Не меняй api.ts, queries.ts, ymaps, server/routes, валидацию ВУ.

Приоритет экранов: onboarding, home, search, create, route.map (карта), trip, bookings, account.
Сохрани file-based routes в src/routes/. BottomCTA forceInPage вместо Telegram MainButton.
```
