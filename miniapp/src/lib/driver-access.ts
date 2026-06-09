import type { ApiUser } from "./api";

export function isActiveDriver(user: ApiUser | null | undefined): boolean {
  return user?.role === "driver" && user.isActiveDriver === true;
}

export function isDriverPending(user: ApiUser | null | undefined): boolean {
  return user?.role === "driver" && user.driverModerationStatus === "pending";
}

export function isDriverRejected(user: ApiUser | null | undefined): boolean {
  return user?.role === "driver" && user.driverModerationStatus === "rejected";
}
