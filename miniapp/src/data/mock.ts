import type { Booking, District, Stop, Trip, User } from "./types";

// Заглушки на этапе статичной верстки. Позже заменяются вызовами API поверх yaride.db.

export const mockUser: User = {
  id: 1,
  name: "Александр",
  username: "alex_yar",
  role: "driver",
  ratingAvg: 4.9,
  ratingCount: 124,
  tripsDriverCount: 124,
  carModel: "Kia Rio",
  carColor: "Белый",
  carPlate: "У723КВ",
};

// 6 районов Ярославля (как в app/seeds.py).
export const districts: District[] = [
  { name: "Дзержинский", icon: "apartment", iconBg: "bg-primary-fixed text-on-primary-fixed-variant" },
  { name: "Заволжский", icon: "pool", iconBg: "bg-secondary-fixed text-on-secondary-fixed-variant" },
  { name: "Кировский", icon: "account_balance", iconBg: "bg-tertiary-fixed text-on-tertiary-fixed-variant" },
  { name: "Красноперекопский", icon: "factory", iconBg: "bg-primary-fixed text-on-primary-fixed-variant" },
  { name: "Ленинский", icon: "architecture", iconBg: "bg-surface-container-high text-on-surface-variant" },
  { name: "Фрунзенский", icon: "directions_bus", iconBg: "bg-secondary-fixed text-on-secondary-fixed-variant" },
];

export const stops: Stop[] = [
  { id: 1, title: "Площадь Труда", adminArea: "Центр", distanceKm: 0.8 },
  { id: 2, title: "Проспект Толбухина", adminArea: "Центр", distanceKm: 1.2 },
  { id: 3, title: "Богоявленская площадь", adminArea: "Центр", distanceKm: 1.5 },
  { id: 4, title: "Площадь Волкова", adminArea: "Центр", distanceKm: 2.1 },
  { id: 5, title: "Красная площадь", adminArea: "Центр", distanceKm: 2.4 },
];

export const trips: Trip[] = [
  {
    id: 101,
    driverName: "Иван",
    driverRating: 4.8,
    driverTripsCount: 124,
    fromTitle: "Кировский (Центр)",
    toTitle: "Заволжский",
    whenLabel: "Сегодня, 18:30",
    priceRub: 150,
    seatsTotal: 4,
    seatsFree: 2,
    carModel: "Kia Rio",
    carColor: "Белый",
    carPlate: "У723КВ",
    driverComment: "Еду через центр, могу забрать у ТЦ Аура. В машине не курим, багажник полупустой.",
  },
  {
    id: 102,
    driverName: "Мария",
    driverRating: 4.9,
    driverTripsCount: 89,
    fromTitle: "Московский проспект",
    toTitle: "Дзержинский (Брагино)",
    whenLabel: "Сегодня, 19:15",
    priceRub: 180,
    seatsTotal: 3,
    seatsFree: 1,
    carModel: "Hyundai Solaris",
    carColor: "Серый",
    carPlate: "К512МН",
  },
  {
    id: 103,
    driverName: "Дмитрий",
    driverRating: 4.7,
    driverTripsCount: 56,
    fromTitle: "Ленинский (Юбилейная пл.)",
    toTitle: "Фрунзенский (Сокол)",
    whenLabel: "Завтра, 08:00",
    priceRub: 120,
    seatsTotal: 4,
    seatsFree: 3,
  },
];

export const bookings: Booking[] = [
  {
    id: 5001,
    tripId: 101,
    fromTitle: "Кировский (Центр)",
    toTitle: "Заволжский",
    whenLabel: "Сегодня, 18:30",
    priceRub: 150,
    status: "active",
  },
  {
    id: 5002,
    tripId: 95,
    fromTitle: "Дзержинский (Брагино)",
    toTitle: "Кировский (Центр)",
    whenLabel: "Вчера, 09:00",
    priceRub: 130,
    status: "cancelled_by_driver",
    cancelReason: "Изменились планы, прошу прощения",
  },
];

export const timeSlots: string[] = (() => {
  const out: string[] = [];
  for (let h = 6; h <= 22; h++) {
    out.push(`${String(h).padStart(2, "0")}:00`);
    out.push(`${String(h).padStart(2, "0")}:30`);
  }
  return out;
})();

export const seatOptions = [2, 3, 4];
export const priceOptions = [100, 150, 200];
