import { useQuery } from "@tanstack/react-query";
import { apiGet, type JobStatus, type StatusResponse } from "@/lib/api/client";
import { formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";

const quoteJobs = (jobs: JobStatus[]) => jobs.filter((job) => job.job.startsWith("quotes_"));

function latestSuccess(jobs: JobStatus[]): string | null {
  const dates = quoteJobs(jobs).map((job) => job.last_success_at).filter((d): d is string => d != null);
  return dates.length ? dates.reduce((a, b) => (a > b ? a : b)) : null;
}

function hasFailingSource(jobs: JobStatus[]): boolean {
  return quoteJobs(jobs).some((job) => job.last_error_at != null && (job.last_success_at == null || job.last_error_at > job.last_success_at));
}

export function MarketStatus() {
  const { data, isError } = useQuery({
    queryKey: ["status"],
    queryFn: () => apiGet<StatusResponse>("/api/status"),
    refetchInterval: 60_000,
  });

  if (isError) return <p className="text-xs font-medium text-down">API injoignable</p>;
  if (!data) return <p className="text-xs text-muted-foreground">Chargement…</p>;

  return (
    <div className="space-y-1 text-xs">
      <p className="flex items-center gap-2 font-medium">
        <span className={cn("size-2 rounded-full", data.market_open ? "bg-up" : "bg-down")} aria-hidden />
        {data.market_open ? "Bourse ouverte" : "Bourse fermée"}
      </p>
      <p className="text-muted-foreground">Cours mis à jour : {formatDateTime(latestSuccess(data.jobs))}</p>
      {hasFailingSource(data.jobs) && (
        <p className="text-amber-700">Source de données indisponible — dernières données affichées</p>
      )}
    </div>
  );
}
