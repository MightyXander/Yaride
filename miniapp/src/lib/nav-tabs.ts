/** Which bottom-nav tab owns this pathname (matches floating-nav activeIndex). */
export type NavTabRoot = "/search" | "/home" | "/account";

const TAB_MATCHES: { root: NavTabRoot; prefixes: string[] }[] = [
  { root: "/search", prefixes: ["/search"] },
  {
    root: "/home",
    prefixes: ["/home", "/bookings", "/favorites", "/history", "/trip", "/manage", "/create"],
  },
  { root: "/account", prefixes: ["/account", "/license", "/notifications"] },
];

export function navTabForPath(pathname: string): NavTabRoot | null {
  if (pathname === "/") return null;
  for (const { root, prefixes } of TAB_MATCHES) {
    if (prefixes.some((p) => pathname === p || pathname.startsWith(p + "/"))) {
      return root;
    }
  }
  return null;
}

/** True when switching between different bottom-nav tabs (incl. from /bookings → /search). */
export function isNavTabSwitch(from: string, to: string): boolean {
  const fromTab = navTabForPath(from);
  const toTab = navTabForPath(to);
  return fromTab !== null && toTab !== null && fromTab !== toTab;
}

/** Set on nav pointerdown — consumed when destination route mounts. */
let pendingNavTabTo: NavTabRoot | null = null;

export function markNavTabSwitch(to: NavTabRoot) {
  pendingNavTabTo = to;
}

export function takePendingNavTabSwitch(to: string): boolean {
  if (pendingNavTabTo !== null && pendingNavTabTo === to) {
    pendingNavTabTo = null;
    return true;
  }
  return false;
}
