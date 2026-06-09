# Yaride Mini App — экраны и компоненты

Только вёрстка: файлы экранов и переиспользуемых компонентов.

---

## Экраны (`src/screens/`)

| Экран | Роут | Файл |
|-------|------|------|
| Имя (онбординг 1/3) | `/onboarding/name` | `onboarding/NameInput.tsx` |
| Роль (онбординг 2/3) | `/onboarding/role` | `onboarding/RoleSelection.tsx` |
| ВУ и авто (онбординг 3/3) | `/onboarding/license` | `onboarding/DriverLicense.tsx` |
| Главная | `/` | `Dashboard.tsx` |
| Выбор района | `/route/district` | `route/SelectDistrict.tsx` |
| Выбор остановки | `/route/stop` | `route/SelectStop.tsx` |
| Выбор на карте | `/route/map` | `route/SelectOnMap.tsx` |
| Результаты поиска | `/search/results` | `search/SearchResults.tsx` |
| Детали поездки | `/ride/:id` | `search/RideDetails.tsx` |
| Подтверждение брони | `/booking/confirm` | `search/BookingConfirmation.tsx` |
| Создать поездку | `/create` | `create/CreateStart.tsx` |
| Публикация шаблона | `/create/publish` | `create/PublishFromTemplate.tsx` |
| Дата и время | `/create/date-time` | `create/DateTimeStep.tsx` |
| Места и цена | `/create/seats-price` | `create/SeatsPriceStep.tsx` |
| Проверка перед публикацией | `/create/review` | `create/ReviewPublish.tsx` |
| Мои брони | `/bookings` | `booking/MyBookings.tsx` |
| Отмена брони | `/booking/cancel` | `booking/CancelBooking.tsx` |
| Управление (водитель) | `/manage` | `manage/MyRides.tsx` |
| Порог рейтинга | `/manage/threshold` | `manage/RatingThreshold.tsx` |
| Брони поездки | `/manage/bookings` | `manage/ManageBookings.tsx` |
| Профиль | `/account` | `account/Account.tsx` |

Роутинг: `src/App.tsx`

---

## Компоненты (`src/components/`)

| Компонент | Файл | Назначение |
|-----------|------|------------|
| Header | `Header.tsx` | Верхняя панель: назад, заголовок, опц. иконка справа |
| BottomNav | `BottomNav.tsx` | Плавающая нижняя навигация (3 таба) |
| BottomActionButton | `BottomActionButton.tsx` | Основная CTA внизу экрана |
| TripCard | `TripCard.tsx` | Карточка поездки в списке + `Avatar` |
| RouteTimeline | `RouteTimeline.tsx` | Маршрут откуда → куда (вертикальная линия) |
| ListRow | `ListRow.tsx` | Строка списка с иконкой и chevron |
| ProgressBar | `ProgressBar.tsx` | Прогресс-бар + подпись шага |
| Calendar | `Calendar.tsx` | Календарь выбора даты |
| Chip | `Chip.tsx` | Чип выбора (дата, время) |
| StarRating | `StarRating.tsx` | Звезда + число рейтинга |
| SeatsIndicator | `SeatsIndicator.tsx` | Иконки занятых/свободных мест |
| StatusBadge | `StatusBadge.tsx` | Бейдж статуса брони |
| Icon | `Icon.tsx` | Material Symbols |
| Screen | `Screen.tsx` | Обёртка main с отступами |
| LoadingView | `States.tsx` | Загрузка |
| ErrorView | `States.tsx` | Ошибка + повтор |
| EmptyView | `States.tsx` | Пустой список |

---

## Структура экранов (блоки)

### Dashboard
- Header «Yaride»
- Профиль (аватар, рейтинг, имя, бейдж)
- Баннер модерации (условно)
- CTA «Создать поездку» (условно)
- Меню list-group (иконка + текст + chevron)
- Промо-баннер с картинкой
- BottomNav

### NameInput / RoleSelection / DriverLicense
- Header + progress bar
- Контент шага (инпут / карточки ролей / поля ВУ)
- BottomActionButton

### SelectDistrict
- Header + progress bar
- Breadcrumb, заголовок
- Кнопка-картинка «На карте»
- Кнопка геолокации, ближайшие остановки
- Список районов
- BottomNav

### SelectStop
- Header, breadcrumb, поиск
- Список остановок

### SelectOnMap
- Header
- Fullscreen карта + поиск + bottom sheet подтверждения

### SearchResults / RideDetails / BookingConfirmation
- Header
- Список TripCard / детали поездки / экран успеха
- BottomActionButton или BottomNav

### CreateStart → ReviewPublish (5 экранов)
- Header (+ ProgressBar на шагах)
- Формы: шаблоны, календарь, чипы, места/цена, сводка
- BottomActionButton

### MyBookings / CancelBooking
- Header
- Карточки броней / форма отмены
- BottomNav или fixed CTA

### MyRides / RatingThreshold / ManageBookings
- Header
- Настройки, список поездок, radio-опции, пассажиры
- BottomNav / FAB / BottomActionButton

### Account
- Header
- Профиль, статистика, отзывы, CTA «Стать водителем»
- BottomNav
