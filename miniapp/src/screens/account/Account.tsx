import { useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Icon } from "../../components/Icon";
import { BottomNav } from "../../components/BottomNav";
import { Avatar } from "../../components/TripCard";
import { LoadingView } from "../../components/States";
import { api } from "../../api/client";
import { useApi } from "../../api/useApi";
import { useUser } from "../../state/UserContext";
import { patchDraft } from "../../state/onboarding";

// Профиль: шапка, рейтинг, полученные оценки, апгрейд до водителя (для пассажира).
export function Account() {
  const navigate = useNavigate();
  const { me } = useUser();
  const loadRatings = useCallback(() => api.ratingsReceived(), []);
  const { data } = useApi(loadRatings, []);

  if (!me?.user) return <LoadingView />;
  const user = me.user;
  const reviews = data?.ratings ?? [];

  const becomeDriver = () => {
    // Переиспользуем экран ВУ; имя берём из текущего профиля, чтобы не вводить заново.
    patchDraft({ name: user.name, role: "driver" });
    navigate("/onboarding/license");
  };

  return (
    <>
      <header className="fixed top-0 left-0 w-full z-50 flex items-center justify-center px-margin-page h-14 bg-surface dark:bg-background border-b border-outline-variant/20">
        <h1 className="font-headline-md text-headline-md-mobile font-bold text-primary dark:text-inverse-primary">Профиль</h1>
      </header>

      <main className="pt-20 pb-24 px-margin-page min-h-screen flex flex-col gap-6">
        <section className="flex flex-col items-center text-center">
          <Avatar name={user.name} url={me.telegram.photoUrl} size={80} />
          <h2 className="font-headline-lg text-headline-lg-mobile text-on-surface mt-3">{user.name}</h2>
          <div className="flex items-center gap-2 mt-1">
            <span className="bg-primary/10 text-primary px-2 py-0.5 rounded-md font-label-sm uppercase tracking-wider">
              {user.role === "driver" ? "Водитель" : "Пассажир"}
            </span>
            {me.telegram.username && <span className="text-outline font-label-md">@{me.telegram.username}</span>}
          </div>
        </section>

        <div className="grid grid-cols-2 gap-4">
          <div className="bg-surface-container-low p-padding-card rounded-xl border border-outline-variant/20">
            <div className="flex items-center gap-1 mb-1">
              <Icon name="star" filled className="text-tertiary text-[18px]" />
              <span className="font-headline-md text-headline-md text-on-surface tabular-nums">
                {user.ratingAvg.toFixed(1)}
              </span>
            </div>
            <p className="font-label-md text-label-md text-on-surface-variant">Средний рейтинг</p>
          </div>
          <div className="bg-surface-container-low p-padding-card rounded-xl border border-outline-variant/20">
            <p className="font-headline-md text-headline-md text-on-surface tabular-nums mb-1">{user.ratingCount}</p>
            <p className="font-label-md text-label-md text-on-surface-variant">Всего оценок</p>
          </div>
        </div>

        <section>
          <h3 className="font-label-md text-label-md text-outline mb-3 uppercase tracking-widest">Оценки обо мне</h3>
          {reviews.length === 0 ? (
            <p className="font-body-md text-body-md text-on-surface-variant">Пока нет оценок.</p>
          ) : (
            <div className="flex flex-col gap-gutter-stack">
              {reviews.map((r, i) => (
                <div key={i} className="bg-surface-container-lowest p-padding-card rounded-xl border border-outline-variant/20">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1">
                      <Icon name="star" filled className="text-tertiary text-[16px]" />
                      <span className="font-body-md text-body-md text-on-surface">{r.stars}</span>
                      {r.fromName && <span className="font-label-md text-label-md text-on-surface-variant ml-1">от {r.fromName}</span>}
                    </div>
                    <span className="font-label-sm text-label-sm text-outline">поездка #{r.tripId}</span>
                  </div>
                  {r.reviewText && <p className="font-body-md text-body-md text-on-surface mt-2 italic">«{r.reviewText}»</p>}
                </div>
              ))}
            </div>
          )}
        </section>

        {user.role === "passenger" && (
          <button
            onClick={becomeDriver}
            className="w-full h-14 rounded-xl bg-primary text-on-primary font-headline-md flex items-center justify-center gap-2 active:scale-95 transition-transform shadow-lg shadow-primary/20"
          >
            <Icon name="directions_car" />
            Стать водителем
          </button>
        )}
      </main>

      <BottomNav />
    </>
  );
}
