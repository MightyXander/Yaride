import { useNavigate } from "react-router-dom";
import { Icon } from "../components/Icon";
import { BottomNav } from "../components/BottomNav";
import { Avatar } from "../components/TripCard";
import { LoadingView } from "../components/States";
import { useUser } from "../state/UserContext";
import { haptic } from "../telegram/webapp";
import heroImg from "../assets/hero.png";

interface Tile {
  icon: string;
  label: string;
  iconColor: string;
  iconBg: string;
  path: string;
  primary?: boolean;
  driverOnly?: boolean;
}

const TILES: Tile[] = [
  { icon: "search", label: "Найти поездки", iconColor: "text-primary", iconBg: "bg-primary/10", path: "/route/district?mode=search&leg=start" },
  { icon: "add", label: "Создать поездку", iconColor: "text-on-primary", iconBg: "bg-on-primary/20", path: "/create", primary: true, driverOnly: true },
  { icon: "confirmation_number", label: "Мои брони", iconColor: "text-secondary", iconBg: "bg-secondary/10", path: "/bookings" },
  { icon: "schedule", label: "История", iconColor: "text-on-surface-variant", iconBg: "bg-outline-variant/20", path: "/bookings" },
  { icon: "star", label: "Маршруты", iconColor: "text-tertiary", iconBg: "bg-tertiary-fixed-dim/20", path: "/route/district?mode=search&leg=start" },
  { icon: "settings", label: "Управление", iconColor: "text-on-surface-variant", iconBg: "bg-surface-container-highest", path: "/manage", driverOnly: true },
];

export function Dashboard() {
  const navigate = useNavigate();
  const { me } = useUser();

  const go = (path: string) => {
    haptic("light");
    navigate(path);
  };

  if (!me?.user) return <LoadingView />;
  const user = me.user;
  const isDriver = user.role === "driver";
  const tiles = TILES.filter((t) => !t.driverOnly || isDriver);

  return (
    <>
      <header className="fixed top-0 left-0 w-full z-50 flex items-center justify-between px-margin-page h-14 bg-surface dark:bg-background border-b border-outline-variant/20">
        <h1 className="font-headline-md text-headline-md-mobile font-bold text-primary dark:text-inverse-primary">Yaride</h1>
        <div className="flex items-center gap-1 bg-secondary/10 px-3 py-1 rounded-full">
          <Icon name="star" filled className="text-secondary text-[16px]" />
          <span className="text-label-md font-label-md text-secondary">{user.ratingAvg.toFixed(1)}</span>
        </div>
      </header>

      <main className="pt-20 pb-24 px-margin-page min-h-screen">
        <section className="mb-8 flex items-center justify-between bg-surface-container-low p-padding-card rounded-xl border border-outline-variant/20">
          <div className="flex items-center gap-4">
            <div className="relative">
              <Avatar name={user.name} url={me.telegram.photoUrl} size={64} />
              <span className="absolute bottom-0 right-0 bg-secondary w-4 h-4 rounded-full border-2 border-surface" />
            </div>
            <div>
              <h2 className="font-headline-md text-headline-md text-on-surface">{user.name}</h2>
              <div className="flex items-center gap-2 mt-1">
                <span className="bg-primary/10 text-primary px-2 py-0.5 rounded-md font-label-sm uppercase tracking-wider">
                  {isDriver ? "Водитель" : "Пассажир"}
                </span>
                <span className="text-outline font-label-md">Ярославль</span>
              </div>
            </div>
          </div>
          <button className="w-10 h-10 rounded-full bg-surface-container-highest flex items-center justify-center active:scale-95 transition-transform">
            <Icon name="notifications" className="text-on-surface-variant" />
          </button>
        </section>

        {isDriver && (
          <div className="grid grid-cols-2 gap-4 mb-8">
            <div className="bg-surface-container-lowest p-4 rounded-xl border border-outline-variant/20 flex flex-col gap-1">
              <span className="text-outline font-label-sm">Поездок водителем</span>
              <span className="font-headline-md text-headline-md text-primary tabular-nums">{user.tripsDriverCount}</span>
            </div>
            <div className="bg-surface-container-lowest p-4 rounded-xl border border-outline-variant/20 flex flex-col gap-1">
              <span className="text-outline font-label-sm">Рейтинг</span>
              <span className="font-headline-md text-headline-md text-secondary tabular-nums">
                {user.ratingAvg.toFixed(2)}
              </span>
            </div>
          </div>
        )}

        <h3 className="font-label-md text-label-md text-outline mb-4 uppercase tracking-widest px-1">Меню управления</h3>
        <div className="grid grid-cols-2 gap-3">
          {tiles.map((t) => (
            <button
              key={t.label}
              onClick={() => go(t.path)}
              className={`flex flex-col items-center justify-center gap-3 p-6 rounded-xl transition-all active:scale-95 ${
                t.primary
                  ? "bg-primary text-on-primary shadow-lg shadow-primary/20"
                  : "bg-surface-container-lowest border border-outline-variant/20"
              }`}
            >
              <div className={`w-12 h-12 rounded-full flex items-center justify-center ${t.iconBg}`}>
                <Icon name={t.icon} className={`${t.iconColor} text-[28px]`} />
              </div>
              <span className={`font-label-md text-label-md text-center ${t.primary ? "font-bold" : "text-on-surface"}`}>
                {t.label}
              </span>
            </button>
          ))}
        </div>

        <div className="mt-8 rounded-xl overflow-hidden relative h-40 active:scale-[0.98] transition-transform bg-gradient-to-br from-primary to-primary-container">
          <img src={heroImg} alt="" className="absolute inset-0 w-full h-full object-cover" aria-hidden />
          <div className="absolute inset-0 bg-gradient-to-t from-on-background/70 via-on-background/20 to-transparent flex flex-col justify-end p-6">
            <span className="bg-secondary text-on-secondary w-fit px-3 py-1 rounded-full font-label-sm mb-2">
              Совет {isDriver ? "водителям" : "пассажирам"}
            </span>
            <h4 className="text-white font-headline-md-mobile">
              {isDriver ? "Как набрать высокий рейтинг и больше попутчиков" : "Как быстро находить попутку по районам Ярославля"}
            </h4>
          </div>
        </div>
      </main>

      <BottomNav />
    </>
  );
}
