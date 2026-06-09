import type { ApiHistoryDriver, ApiHistoryPassenger } from "./api";

export type BookingBadgeStatus =
  | "active"
  | "cancelled_by_passenger"
  | "cancelled_by_driver"
  | "completed";

export function passengerHistoryBadgeStatus(item: ApiHistoryPassenger): BookingBadgeStatus {
  if (
    item.bookingStatus === "cancelled_by_passenger" ||
    item.bookingStatus === "cancelled_by_driver"
  ) {
    return item.bookingStatus;
  }
  if (item.tripStatus === "completed" || item.bookingStatus !== "active") {
    return "completed";
  }
  return "active";
}

export function driverHistoryBadgeStatus(item: ApiHistoryDriver): BookingBadgeStatus {
  if (item.tripStatus === "cancelled") return "cancelled_by_driver";
  if (item.tripStatus === "completed") return "completed";
  return "active";
}
