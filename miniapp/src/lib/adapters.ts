import type { ApiTrip } from "./api";

/** Card shape for TripCard / lists (labels instead of mock stop ids). */
export interface TripCardData {
  id: string;
  driverName: string;
  driverRating: number;
  fromLabel: string;
  fromSub?: string;
  toLabel: string;
  toSub?: string;
  date: string;
  time: string;
  price: number;
  seatsTotal: number;
  seatsTaken: number;
}

export function apiTripToCard(t: ApiTrip): TripCardData {
  const seatsBooked = t.seatsBooked ?? Math.max(0, t.seatsTotal - t.seatsFree);
  const departureTime =
    t.departureTime?.trim() ||
    t.whenLabel?.match(/(\d{1,2}:\d{2})\s*$/)?.[1] ||
    "";
  return {
    id: String(t.id),
    driverName: t.driverName ?? "Водитель",
    driverRating: t.driverRating ?? 0,
    fromLabel: t.fromTitle,
    toLabel: t.toTitle,
    date: t.tripDate ?? "",
    time: departureTime,
    price: t.priceRub,
    seatsTotal: t.seatsTotal,
    seatsTaken: seatsBooked,
  };
}
