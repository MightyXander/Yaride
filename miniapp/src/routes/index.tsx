import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { meQueryOptions } from "@/lib/queries";

export const Route = createFileRoute("/")({
  component: Index,
});

function Index() {
  const navigate = useNavigate();
  const { data, isLoading, isError, isFetching, failureCount } = useQuery(meQueryOptions());

  useEffect(() => {
    if (isLoading || (isFetching && !data)) return;
    if (isError && !data) return;
    const t = setTimeout(() => {
      navigate({ to: data?.registered ? "/home" : "/onboarding", replace: true });
    }, 50);
    return () => clearTimeout(t);
  }, [navigate, data, isLoading, isError, isFetching, failureCount]);

  return (
    <div className="min-h-dvh flex items-center justify-center bg-background">
      <div className="flex flex-col items-center gap-3">
        <div className="size-16 rounded-2xl bg-primary text-primary-foreground grid place-items-center text-2xl font-black">
          Y
        </div>
        <div className="text-sm text-muted-foreground">
          {isError && !data ? "Не удалось войти. Закройте и откройте приложение снова." : "Yaride"}
        </div>
      </div>
    </div>
  );
}
