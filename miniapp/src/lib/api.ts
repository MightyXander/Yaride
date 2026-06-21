/** Typed HTTP client for Yaride Mini App API (Telegram X-Init-Data auth). */

import { bootstrapInitData, getInitData, refreshInitData, waitForInitData } from "./init-data";
import { apiBaseUrl } from "./runtime-api-url";

let initDataProvider: () => string = getInitData;

export function setInitDataProvider(fn: () => string) {
  initDataProvider = fn;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}, attempt = 0): Promise<T> {
  await bootstrapInitData();
  refreshInitData();

  const initData = initDataProvider();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (initData) headers["X-Init-Data"] = initData;

  const res = await fetch(`${apiBaseUrl()}${path}`, { ...options, headers });
  if (res.status === 401 && attempt < 2) {
    await waitForInitData(2500);
    return request<T>(path, options, attempt + 1);
  }
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) {
        detail =
          typeof body.detail === "string"
            ? body.detail
            : Array.isArray(body.detail)
              ? body.detail.map((x: { msg?: string }) => x.msg ?? String(x)).join("; ")
              : String(body.detail);
      }
    } catch {
      /* not json */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export type Role = "driver" | "passenger";

export interface ApiUser {
  id: number;
  tgUserId: number;
  name: string;
  username?: string;
  role: Role;
  ratingAvg: number;
  ratingCount: number;
  tripsDriverCount: number;
  tripsPassengerCount: number;
  carModel?: string;
  carColor?: string;
  carPlate?: string;
  minPassengerRating?: number | null;
  driverModerationStatus?: "pending" | "approved" | "rejected";
  isActiveDriver?: boolean;
  dlSeriesNumber?: string;
  dlValidUntil?: string;
  isBanned?: boolean;
}

export interface MeResponse {
  registered: boolean;
  user: ApiUser | null;
  telegram: { id: number; name: string; username?: string; photoUrl?: string };
}

export interface ApiTrip {
  id: number;
  fromTitle: string;
  toTitle: string;
  tripDate?: string;
  departureTime?: string;
  whenLabel: string;
  priceRub: number;
  seatsTotal: number;
  seatsFree: number;
  seatsBooked?: number;
  status: string;
  driverName?: string;
  driverUsername?: string | null;
  driverRating: number;
  driverRatingCount?: number;
  driverTripsCount?: number;
  driverCreatedAt?: string;
  comment?: string;
  carModel?: string;
  carColor?: string;
  carPlate?: string;
  startLat?: number;
  startLng?: number;
  endLat?: number;
  endLng?: number;
}

export interface ApiBooking {
  id: number;
  tripId: number;
  status: string;
  cancelReason?: string;
  fromTitle: string;
  toTitle: string;
  whenLabel: string;
  priceRub: number;
  driverName?: string;
  startLat?: number;
  startLng?: number;
  endLat?: number;
  endLng?: number;
}

export interface ApiFavorite {
  id: number;
  startPointId: number;
  endPointId: number;
  fromTitle: string;
  toTitle: string;
}

export interface ApiHistoryPassenger {
  bookingId: number;
  tripId: number;
  bookingStatus: string;
  tripStatus: string;
  cancelReason?: string;
  fromTitle: string;
  toTitle: string;
  tripDate?: string;
  departureTime?: string;
  whenLabel: string;
  priceRub: number;
  seatsTotal: number;
  seatsFree: number;
  driverName?: string;
  driverRating: number;
  driverTgUserId?: number;
  myRatingStars?: number | null;
  canRate: boolean;
}

export interface ApiHistoryDriver {
  tripId: number;
  tripStatus: string;
  fromTitle: string;
  toTitle: string;
  tripDate?: string;
  departureTime?: string;
  whenLabel: string;
  priceRub: number;
  seatsTotal: number;
  seatsBooked: number;
  seatsFree: number;
}

export interface ApiPendingRating {
  tripId: number;
  ratedTgUserId: number;
  ratedName: string;
  fromTitle?: string;
  toTitle?: string;
  whenLabel?: string;
  driverName?: string;
}

export interface ApiNotification {
  id: string;
  kind: "booking" | "rating" | "cancel" | "system";
  title: string;
  body: string;
  occurredAt: string;
  unread?: boolean;
  tripId?: number;
  action?: "rate" | "manage" | "bookings" | "trip";
}

export interface ApiStop {
  id: number;
  title: string;
  adminArea: string;
  locality?: string;
  district?: string;
}

export interface ApiTemplate {
  id: number;
  startPointId: number;
  endPointId: number;
  fromTitle: string;
  toTitle: string;
  priceRub: number;
  seatsTotal: number;
  comment?: string | null;
}

export interface ApiMapStop extends ApiStop {
  district?: string | null;
  lat: number;
  lng: number;
}

export const api = {
  me: () => request<MeResponse>("/api/me"),

  register: (body: {
    name: string;
    role: Role;
    dl_series_number?: string;
    dl_valid_until?: string;
    car_model?: string;
    car_color?: string;
    car_plate?: string;
  }) =>
    request<{ registered: boolean; user: ApiUser | null }>("/api/register", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  districts: () => request<{ districts: string[] }>("/api/catalog/districts"),
  stops: (district: string) =>
    request<{ stops: ApiStop[] }>(`/api/catalog/stops?district=${encodeURIComponent(district)}`),
  allStops: () => request<{ stops: ApiMapStop[] }>("/api/catalog/stops/all"),

  searchTrips: (params: {
    start_point?: number;
    end_point?: number;
    start_district?: string;
    end_district?: string;
    date?: string;
  }) => {
    const qs = new URLSearchParams();
    if (params.start_point) qs.set("start_point", String(params.start_point));
    if (params.end_point) qs.set("end_point", String(params.end_point));
    if (params.start_district) qs.set("start_district", params.start_district);
    if (params.end_district) qs.set("end_district", params.end_district);
    if (params.date) qs.set("date", params.date);
    return request<{
      trips: ApiTrip[];
      searchScope?: "exact" | "district";
      districtFallback?: { startDistrict: string; endDistrict: string };
    }>(`/api/trips?${qs.toString()}`);
  },

  trip: (id: number) => request<ApiTrip>(`/api/trips/${id}`),

  createTrip: (body: {
    start_point_id: number;
    end_point_id: number;
    trip_date: string;
    departure_time: string;
    price_rub: number;
    seats_total: number;
    comment?: string;
  }) => request<{ id: number }>("/api/trips", { method: "POST", body: JSON.stringify(body) }),

  nearestStops: (lat: number, lng: number) =>
    request<{
      stops: { id: number; title: string; district?: string; adminArea?: string; distanceKm: number }[];
    }>(`/api/trips/nearby/by-geo?lat=${lat}&lng=${lng}`),

  myBookings: () => request<{ bookings: ApiBooking[] }>("/api/bookings"),
  book: (tripId: number) =>
    request<{ id: number }>("/api/bookings", { method: "POST", body: JSON.stringify({ trip_id: tripId }) }),
  cancelBooking: (bookingId: number, reason: string) =>
    request<{ ok: boolean }>(`/api/bookings/${bookingId}/cancel`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),

  manageTrips: () => request<{ trips: ApiTrip[] }>("/api/manage/trips"),
  manageTripBookings: (tripId: number) =>
    request<{
      bookings: {
        bookingId: number;
        status: string;
        passengerName?: string;
        passengerRating?: number;
      }[];
    }>(`/api/manage/trips/${tripId}/bookings`),
  rejectBooking: (bookingId: number) =>
    request<{ ok: boolean; passengerTgUserId?: number }>(
      `/api/manage/bookings/${bookingId}/reject`,
      { method: "POST" },
    ),
  cancelTrip: (tripId: number) =>
    request<{ ok: boolean; affectedPassengers: number[] }>(`/api/manage/trips/${tripId}/cancel`, {
      method: "POST",
    }),
  setPassengerRatingThreshold: (threshold: "3.0" | "4.0" | "4.5" | "off") =>
    request<{ ok: boolean; minPassengerRating: number | null }>("/api/manage/passenger-rating-threshold", {
      method: "PUT",
      body: JSON.stringify({ threshold }),
    }),

  favorites: () => request<{ favorites: ApiFavorite[] }>("/api/favorites"),
  addFavorite: (body: { trip_id?: number; start_point_id?: number; end_point_id?: number }) =>
    request<{ added: boolean }>("/api/favorites", { method: "POST", body: JSON.stringify(body) }),
  deleteFavorite: (id: number) => request<{ ok: boolean }>(`/api/favorites/${id}`, { method: "DELETE" }),

  history: (role: "passenger" | "driver" = "passenger") =>
    request<{ role: string; items: ApiHistoryPassenger[] | ApiHistoryDriver[] }>(
      `/api/history?role=${role}`,
    ),

  ratingsReceived: () =>
    request<{
      ratings: { stars: number; tripId: number; reviewText?: string; createdAt?: string; fromName?: string }[];
    }>("/api/ratings/received"),
  ratingsPending: () => request<{ pending: ApiPendingRating[] }>("/api/ratings/pending"),
  notifications: () => request<{ notifications: ApiNotification[] }>("/api/notifications"),
  submitRating: (body: { trip_id: number; rated_tg_user_id: number; stars: number; review_text?: string }) =>
    request<{ ok: boolean }>("/api/ratings", { method: "POST", body: JSON.stringify(body) }),

  createAlert: (body: {
    from_point_id: number;
    to_point_id: number;
    desired_date: string;
    desired_time?: string;
  }) => request<{ id: number }>("/api/alerts", { method: "POST", body: JSON.stringify(body) }),

  templates: () => request<{ templates: ApiTemplate[] }>("/api/templates"),
  createTemplate: (body: {
    start_point_id: number;
    end_point_id: number;
    price_rub: number;
    seats_total: number;
    comment?: string;
  }) => request<{ id: number }>("/api/templates", { method: "POST", body: JSON.stringify(body) }),
  deleteTemplate: (id: number) =>
    request<{ ok: boolean }>(`/api/templates/${id}`, { method: "DELETE" }),
  publishTemplate: (
    id: number,
    body: { trip_date: string; departure_time: string },
  ) =>
    request<{ id: number }>(`/api/templates/${id}/publish`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
