// HTTP-клиент Mini App API. Все запросы несут X-Init-Data (WebApp.initData) для авторизации.
// База берётся из VITE_API_BASE (по умолчанию пусто → относительные пути через Vite-прокси).

import { getWebApp } from "../telegram/webapp";

const BASE = import.meta.env.VITE_API_BASE ?? "";

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const initData = getWebApp()?.initData ?? "";
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (initData) headers["X-Init-Data"] = initData;

  const res = await fetch(`${BASE}${path}`, { ...options, headers });
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

export interface MeResponse {
  registered: boolean;
  user: ApiUser | null;
  telegram: { id: number; name: string; username?: string; photoUrl?: string };
}

export interface ApiUser {
  id: number;
  tgUserId: number;
  name: string;
  username?: string;
  role: "driver" | "passenger";
  ratingAvg: number;
  ratingCount: number;
  tripsDriverCount: number;
  carModel?: string;
  carColor?: string;
  carPlate?: string;
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
  status: string;
  driverName?: string;
  driverRating: number;
  driverTripsCount?: number;
  comment?: string;
  carModel?: string;
  carColor?: string;
  carPlate?: string;
}

export interface ApiTemplate {
  id: number;
  startPointId: number;
  endPointId: number;
  fromTitle: string;
  toTitle: string;
  priceRub: number;
  seatsTotal: number;
  comment?: string;
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
}

export const api = {
  me: () => request<MeResponse>("/api/me"),
  register: (body: {
    name: string;
    role: "driver" | "passenger";
    dl_series_number?: string;
    dl_valid_until?: string;
    car_model?: string;
    car_color?: string;
    car_plate?: string;
  }) => request<{ registered: boolean; user: ApiUser | null }>("/api/register", {
    method: "POST",
    body: JSON.stringify(body),
  }),

  districts: () => request<{ districts: string[] }>("/api/catalog/districts"),
  stops: (district: string) =>
    request<{ stops: { id: number; title: string; adminArea: string }[] }>(
      `/api/catalog/stops?district=${encodeURIComponent(district)}`,
    ),

  searchTrips: (params: { start_point?: number; end_point?: number; date?: string }) => {
    const qs = new URLSearchParams();
    if (params.start_point) qs.set("start_point", String(params.start_point));
    if (params.end_point) qs.set("end_point", String(params.end_point));
    if (params.date) qs.set("date", params.date);
    return request<{ trips: ApiTrip[] }>(`/api/trips?${qs.toString()}`);
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

  myBookings: () => request<{ bookings: ApiBooking[] }>("/api/bookings"),
  book: (tripId: number) =>
    request<{ id: number }>("/api/bookings", { method: "POST", body: JSON.stringify({ trip_id: tripId }) }),
  cancelBooking: (bookingId: number, reason: string) =>
    request<{ ok: boolean }>(`/api/bookings/${bookingId}/cancel`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),

  nearestStops: (lat: number, lng: number) =>
    request<{ stops: { id: number; title: string; district?: string; distanceKm?: number }[] }>(
      `/api/trips/nearby/by-geo?lat=${lat}&lng=${lng}`,
    ),

  manageTrips: () => request<{ trips: ApiTrip[] }>("/api/manage/trips"),
  manageTripBookings: (tripId: number) =>
    request<{ bookings: { bookingId: number; status: string; passengerName?: string; passengerRating?: number }[] }>(
      `/api/manage/trips/${tripId}/bookings`,
    ),
  rejectBooking: (bookingId: number) =>
    request<{ ok: boolean }>(`/api/manage/bookings/${bookingId}/reject`, { method: "POST" }),
  cancelTrip: (tripId: number) =>
    request<{ ok: boolean; affectedPassengers: number[] }>(`/api/manage/trips/${tripId}/cancel`, {
      method: "POST",
    }),

  favorites: () =>
    request<{ favorites: { id: number; startPointId: number; endPointId: number; fromTitle: string; toTitle: string }[] }>(
      "/api/favorites",
    ),
  addFavorite: (body: { trip_id?: number; start_point_id?: number; end_point_id?: number }) =>
    request<{ added: boolean }>("/api/favorites", { method: "POST", body: JSON.stringify(body) }),
  deleteFavorite: (id: number) => request<{ ok: boolean }>(`/api/favorites/${id}`, { method: "DELETE" }),

  templates: () =>
    request<{ templates: ApiTemplate[] }>("/api/templates"),
  createTemplate: (body: {
    start_point_id: number;
    end_point_id: number;
    price_rub: number;
    seats_total: number;
    comment?: string;
  }) => request<{ id: number }>("/api/templates", { method: "POST", body: JSON.stringify(body) }),
  deleteTemplate: (id: number) => request<{ ok: boolean }>(`/api/templates/${id}`, { method: "DELETE" }),
  publishTemplate: (id: number, body: { trip_date: string; departure_time: string }) =>
    request<{ id: number }>(`/api/templates/${id}/publish`, { method: "POST", body: JSON.stringify(body) }),

  submitRating: (body: { trip_id: number; rated_tg_user_id: number; stars: number; review_text?: string }) =>
    request<{ ok: boolean }>("/api/ratings", { method: "POST", body: JSON.stringify(body) }),
  ratingsReceived: () =>
    request<{ ratings: { stars: number; tripId: number; reviewText?: string; createdAt?: string; fromName?: string }[] }>(
      "/api/ratings/received",
    ),
};

export { ApiError };
