export type Role = "driver" | "passenger";

export interface User {
  id: number;
  name: string;
  username?: string;
  role: Role;
  ratingAvg: number;
  ratingCount: number;
  tripsDriverCount: number;
  photoUrl?: string;
  // Поля, добавляемые под дизайн (миграция БД на стороне бэкенда):
  carModel?: string;
  carColor?: string;
  carPlate?: string;
}

export interface Trip {
  id: number;
  driverName: string;
  driverRating: number;
  driverPhotoUrl?: string;
  driverTripsCount?: number;
  fromTitle: string;
  toTitle: string;
  whenLabel: string;
  priceRub: number;
  seatsTotal: number;
  seatsFree: number;
  carModel?: string;
  carColor?: string;
  carPlate?: string;
  driverComment?: string;
}

export type BookingState = "active" | "cancelled_by_passenger" | "cancelled_by_driver";

export interface Booking {
  id: number;
  tripId: number;
  fromTitle: string;
  toTitle: string;
  whenLabel: string;
  priceRub: number;
  status: BookingState;
  cancelReason?: string;
}

export interface District {
  name: string;
  icon: string;
  iconBg: string;
}

export interface Stop {
  id: number;
  title: string;
  adminArea: string;
  distanceKm?: number;
}
