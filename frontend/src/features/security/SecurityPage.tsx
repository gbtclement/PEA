import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useLocation, useNavigate, useParams } from "react-router";
import { FavoriteButton } from "@/components/FavoriteButton";
import { AskAiButton } from "@/features/assistant/AskAiButton";
import { loginPath } from "@/features/auth/redirect";
import { useMe } from "@/features/auth/useMe";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EnvelopeBadges } from "@/features/explorer/EnvelopeBadges";
import { ENVELOPE_LABELS } from "@/lib/envelopes";
import { OrderDialog } from "@/features/portfolio/OrderDialog";
import { ApiError, apiGet, type SecurityDetail } from "@/lib/api/client";
import { currencyUnit, formatDateTime, formatPct, formatPrice } from "@/lib/format";
import { cn } from "@/lib/utils";
import { ForecastCard } from "./ForecastCard";
import { FundamentalsCard } from "./FundamentalsCard";
import { NewsCard } from "./NewsCard";
import { PriceAlertButton } from "./PriceAlertButton";
import { PriceChartPanel } from "./PriceChartPanel";
import { ScoreCard } from "./ScoreCard";
import { SimulatorCard } from "./SimulatorCard";
import { breadcrumb, corporation, DEFAULT_DESCRIPTION, investmentFund, SITE_NAME } from "@/seo/schema";
import { usePageMeta, type PageMeta } from "@/seo/usePageMeta";

const envelopeText = (codes: string[]) =>
  codes.length ? `Enveloppes compatibles : ${codes.map((c) => ENVELOPE_LABELS[c]).join(", ")}.` : "";

function securityMeta(data: SecurityDetail | undefined, error: Error | null): PageMeta {
  if (!data) {
    return { title: error ? "Titre introuvable" : "Chargement", description: DEFAULT_DESCRIPTION, noindex: !!error };
  }
  const etf = data.kind === "etf";
  const section = etf ? { name: "ETF", path: "/etf" } : { name: "Explorer", path: "/explorer" };
  const score = data.score != null ? `score ${SITE_NAME} ${Math.round(data.score)}/100, ` : "";
  return {
    title: `${data.name} (${data.symbol}) — cours, score et analyse`,
    description: `${data.name} (${data.symbol}, ${data.market}) : cours, ${score}graphique en chandeliers, ${etf ? "" : "données fondamentales, "}actualités et simulateur. ${envelopeText(data.envelopes)}`,
    path: `/titres/${data.id}`,
    jsonLd: [
      ...(data.kind === "index" ? [] : [etf ? investmentFund(data) : corporation(data)]),
      breadcrumb([{ name: "Accueil", path: "/" }, section, { name: data.name, path: `/titres/${data.id}` }]),
    ],
  };
}

export function SecurityPage() {
  const id = Number(useParams().id);
  const [ordering, setOrdering] = useState(false);
  const { me } = useMe();
  const navigate = useNavigate();
  const location = useLocation();
  const { data, isPending, error } = useQuery({
    queryKey: ["security", id],
    queryFn: () => apiGet<SecurityDetail>(`/api/securities/${id}`),
    refetchInterval: 60_000,
    retry: (count, err) => !(err instanceof ApiError && err.status === 404) && count < 2,
  });
  usePageMeta(securityMeta(data, error));

  if (isPending) return <Skeleton className="h-96 w-full" />;
  if (error || !data) {
    return (
      <section className="py-20 text-center">
        <p className="text-lg font-medium">{error instanceof ApiError && error.status === 404 ? "Titre introuvable." : "Impossible de charger ce titre."}</p>
        <Link to="/explorer" className="mt-2 inline-block text-sm text-primary">Retour à l'explorateur</Link>
      </section>
    );
  }
  const change = data.change_pct ?? 0;
  return (
    <section className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-semibold tracking-tight">{data.name}</h1>
            <FavoriteButton securityId={data.id} isFavorite={data.is_favorite} />
            {data.kind !== "index" && (
              <>
                <Button variant="outline" size="sm" className="ml-2" onClick={() => (me === null ? navigate(loginPath(location)) : setOrdering(true))}>+ J'ai acheté</Button>
                <AskAiButton security={{ id: data.id, name: data.name }} label />
                <PriceAlertButton security={{ id: data.id, name: data.name, price: data.price, currency: data.currency }} />
              </>
            )}
          </div>
          <p className="mt-1 flex items-center gap-2 text-sm text-muted-foreground">
            {data.symbol} · {data.market}{data.isin && ` · ${data.isin}`} <EnvelopeBadges codes={data.envelopes} />
          </p>
          {data.kind !== "index" && (
            <p className="mt-1 text-xs text-muted-foreground">
              Enveloppes déduites automatiquement (pays du siège, taille de l'entreprise) : à confirmer auprès de votre banque ou courtier.
            </p>
          )}
        </div>
        <div className="text-right">
          <p className="text-3xl font-semibold">{formatPrice(data.price)} {currencyUnit(data.currency)}</p>
          <p className={cn("text-sm font-medium", change > 0 && "text-up", change < 0 && "text-down")}>{formatPct(data.change_pct)} aujourd'hui</p>
          <p className="text-xs text-muted-foreground">Mis à jour {formatDateTime(data.as_of)}</p>
        </div>
      </header>
      <PriceChartPanel key={data.id} securityId={data.id} />
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2 [&>*]:min-w-0">
        <ScoreCard detail={data} />
        <FundamentalsCard detail={data} />
        <SimulatorCard securityId={data.id} />
        {data.kind === "stock" && <ForecastCard securityId={data.id} />}
        <NewsCard securityId={data.id} className={data.kind === "stock" ? "xl:col-span-2" : undefined} />
      </div>
      <OrderDialog open={ordering} onOpenChange={setOrdering}
                   security={{ id: data.id, name: data.name, symbol: data.symbol, currency: data.currency, price: data.price }}
                   price={data.currency === "EUR" ? data.price : null} />
    </section>
  );
}
