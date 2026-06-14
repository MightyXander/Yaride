/** Какой таб нижней навигации владеет pathname (2 таба: Поездки / Профиль). */
export type NavTabRoot = "/home" | "/account";

const TAB_MATCHES: { root: NavTabRoot; prefixes: string[] }[] = [
  {
    root: "/home",
    prefixes: [
      "/home",
      "/search",
      "/bookings",
      "/favorites",
      "/history",
      "/trip",
      "/manage",
      "/create",
    ],
  },
  { root: "/account", prefixes: ["/account", "/license", "/notifications"] },
];

export function navTabForPath(pathname: string): NavTabRoot | null {
  if (pathname === "/") return null;
  for (const { root, prefixes } of TAB_MATCHES) {
    if (prefixes.some((p) => pathname === p || pathname.startsWith(`${p}/`))) {
      return root;
    }
  }
  return null;
}

/** Переключение между разными табами нижней навигации. */
export function isNavTabSwitch(from: string, to: string): boolean {
  const fromTab = navTabForPath(from);
  const toTab = navTabForPath(to);
  return fromTab !== null && toTab !== null && fromTab !== toTab;
}

/** Выставляется на pointerdown таба — читается при монтировании целевого роута. */
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
