import { RouteTimeline } from "./RouteTimeline";
import { SeatsIndicator } from "./SeatsIndicator";
import { StarRating } from "./StarRating";

// Минимальная структура для карточки — совместима и с mock Trip, и с ApiTrip.
export interface TripCardData {
  fromTitle: string;
  toTitle: string;
  whenLabel: string;
  priceRub: number;
  seatsTotal: number;
  seatsFree: number;
  driverName?: string;
  driverRating: number;
  driverPhotoUrl?: string;
}

interface TripCardProps {
  trip: TripCardData;
  selected?: boolean;
  onClick?: () => void;
}

// Карточка поездки в результатах поиска: водитель+рейтинг, цена/время, маршрут, места.
export function TripCard({ trip, selected = false, onClick }: TripCardProps) {
  return (
    <div
      onClick={onClick}
      className={`bg-surface-container-low border rounded-xl p-padding-card transition-all duration-200 active:scale-[0.98] cursor-pointer ${
        selected ? "border-primary outline outline-2 outline-primary bg-primary-fixed/30" : "border-outline-variant/20"
      }`}
    >
      <div className="flex justify-between items-start mb-3">
        <div className="flex items-center gap-3">
          <Avatar name={trip.driverName ?? "?"} url={trip.driverPhotoUrl} />
          <div>
            <p className="font-label-md text-label-md text-on-surface">{trip.driverName ?? "Водитель"}</p>
            <StarRating value={trip.driverRating} />
          </div>
        </div>
        <div className="text-right">
          <p className="font-headline-md text-headline-md text-primary tabular-nums">{trip.priceRub} руб.</p>
          <p className="text-label-sm font-label-sm text-on-surface-variant">{trip.whenLabel}</p>
        </div>
      </div>

      <RouteTimeline from={trip.fromTitle} to={trip.toTitle} />

      <div className="mt-4 flex justify-between items-center pt-3 border-t border-outline-variant/10">
        <SeatsIndicator total={trip.seatsTotal} free={trip.seatsFree} />
        <div className="bg-secondary/10 px-3 py-1 rounded-full">
          <span className="text-label-sm font-label-sm text-secondary">
            {trip.seatsFree} {seatWord(trip.seatsFree)} свободно
          </span>
        </div>
      </div>
    </div>
  );
}

function seatWord(n: number): string {
  if (n % 10 === 1 && n % 100 !== 11) return "место";
  if ([2, 3, 4].includes(n % 10) && ![12, 13, 14].includes(n % 100)) return "места";
  return "мест";
}

// Аватар: фото из Telegram или инициал на цветном фоне.
export function Avatar({ name, url, size = 40 }: { name: string; url?: string; size?: number }) {
  if (url) {
    return (
      <img
        src={url}
        alt={name}
        className="rounded-full object-cover"
        style={{ width: size, height: size }}
      />
    );
  }
  return (
    <div
      className="rounded-full bg-primary-container text-on-primary flex items-center justify-center font-semibold"
      style={{ width: size, height: size, fontSize: size * 0.4 }}
    >
      {name.charAt(0).toUpperCase()}
    </div>
  );
}
