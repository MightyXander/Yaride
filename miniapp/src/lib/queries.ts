import { queryOptions } from "@tanstack/react-query";
import { api } from "./api";

export const queryKeys = {
  me: ["me"] as const,
  districts: ["catalog", "districts"] as const,
  stops: (district: string) => ["catalog", "stops", district] as const,
  allStops: ["catalog", "allStops"] as const,
  searchTrips: (params: Record<string, unknown>) => ["trips", "search", params] as const,
  trip: (id: number) => ["trips", id] as const,
  bookings: ["bookings"] as const,
  manageTrips: ["manage", "trips"] as const,
  manageBookings: (tripId: number) => ["manage", "bookings", tripId] as const,
  favorites: ["favorites"] as const,
  history: (role: "passenger" | "driver") => ["history", role] as const,
  ratingsReceived: ["ratings", "received"] as const,
  ratingsPending: ["ratings", "pending"] as const,
  notifications: ["notifications"] as const,
  templates: ["templates"] as const,
};

export const meQueryOptions = () =>
  queryOptions({
    queryKey: queryKeys.me,
    queryFn: () => api.me(),
    staleTime: 5 * 60_000,
    gcTime: 30 * 60_000,
  });

export const districtsQueryOptions = () =>
  queryOptions({
    queryKey: queryKeys.districts,
    queryFn: () => api.districts(),
    staleTime: 5 * 60_000,
  });

export const stopsQueryOptions = (district: string) =>
  queryOptions({
    queryKey: queryKeys.stops(district),
    queryFn: () => api.stops(district),
    enabled: !!district,
    staleTime: 5 * 60_000,
  });

export const bookingsQueryOptions = () =>
  queryOptions({
    queryKey: queryKeys.bookings,
    queryFn: () => api.myBookings(),
    staleTime: 5 * 60_000,
  });

export const favoritesQueryOptions = () =>
  queryOptions({
    queryKey: queryKeys.favorites,
    queryFn: () => api.favorites(),
    staleTime: 5 * 60_000,
  });

export const manageTripsQueryOptions = () =>
  queryOptions({
    queryKey: queryKeys.manageTrips,
    queryFn: () => api.manageTrips(),
    staleTime: 5 * 60_000,
  });

export const historyQueryOptions = (role: "passenger" | "driver") =>
  queryOptions({
    queryKey: queryKeys.history(role),
    queryFn: () => api.history(role),
    staleTime: 5 * 60_000,
  });

export const tripQueryOptions = (id: number) =>
  queryOptions({
    queryKey: queryKeys.trip(id),
    queryFn: () => api.trip(id),
    enabled: id > 0,
  });

export const ratingsReceivedQueryOptions = () =>
  queryOptions({
    queryKey: queryKeys.ratingsReceived,
    queryFn: () => api.ratingsReceived(),
  });

export const allStopsQueryOptions = () =>
  queryOptions({
    queryKey: queryKeys.allStops,
    queryFn: () => api.allStops(),
    staleTime: 5 * 60_000,
  });

export const ratingsPendingQueryOptions = () =>
  queryOptions({
    queryKey: queryKeys.ratingsPending,
    queryFn: () => api.ratingsPending(),
  });

export const notificationsQueryOptions = () =>
  queryOptions({
    queryKey: queryKeys.notifications,
    queryFn: () => api.notifications(),
    staleTime: 30_000,
  });

export const templatesQueryOptions = () =>
  queryOptions({
    queryKey: queryKeys.templates,
    queryFn: () => api.templates(),
    staleTime: 5 * 60_000,
  });

export const manageBookingsQueryOptions = (tripId: number) =>
  queryOptions({
    queryKey: queryKeys.manageBookings(tripId),
    queryFn: () => api.manageTripBookings(tripId),
    enabled: tripId > 0,
  });
