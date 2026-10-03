import { usePageMeta } from "@/seo/usePageMeta";
import { useMemo, useState } from "react";
import { EChart } from "@/components/charts/EChart";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { OrderOut, PortfolioOut } from "@/lib/api/client";
import { formatPct, formatPrice } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useOrders, usePortfolio, usePortfolioHistory } from "./api";
import { buildAllocationOption, buildHistoryOption } from "./charts";
import { OrderCounterCard } from "./OrderCounterCard";
import { OrderDialog } from "./OrderDialog";
import { OrdersHistory } from "./OrdersHistory";
import { PositionsTable } from "./PositionsTable";
import { SITE_NAME } from "@/seo/schema";

type DialogState = { open: boolean; order?: OrderOut };

const signed = (value: number) => `${value > 0 ? "+" : ""}${formatPrice(value)} €`;

function Kpi({ label, value, sub, tone = 0 }: { label: string; value: string; sub?: string; tone?: number }) {
  return (
    <Card>
      <CardContent className="space-y-1">
        <p className="text-xs font-medium text-muted-foreground">{label}</p>
        <p className={cn("text-2xl font-semibold tabular-nums", tone > 0 && "text-up", tone < 0 && "text-down")}>{value}</p>
        {sub && <p className={cn("text-xs tabular-nums", tone > 0 ? "text-up" : tone < 0 ? "text-down" : "text-muted-foreground")}>{sub}</p>}
      </CardContent>
    </Card>
  );
}

function KeyFigures({ data }: { data: PortfolioOut }) {
  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      <Kpi label="Valeur totale" value={`${formatPrice(data.total_value)} €`} />
      <Kpi label="Montant investi" value={`${formatPrice(data.invested)} €`} sub="frais d'achat inclus" />
      <Kpi label="Plus/moins-value" value={signed(data.gain)} sub={formatPct(data.gain_pct)} tone={data.gain} />
      <Kpi label="Variation du jour" value={signed(data.day_change)} sub={formatPct(data.day_change_pct)} tone={data.day_change} />
    </div>
  );
}

function Charts({ data }: { data: PortfolioOut }) {
  const history = usePortfolioHistory();
  const byTitle = useMemo(() => buildAllocationOption(data.positions.map((p) => ({ name: p.name, value: p.value }))), [data.positions]);
  const bySector = useMemo(() => buildAllocationOption(data.sectors.map((s) => ({ name: s.sector, value: s.value }))), [data.sectors]);
  const evolution = useMemo(() => buildHistoryOption(history.data ?? []), [history.data]);
  return (
    <>
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <Card>
          <CardHeader><CardTitle className="text-base">Répartition par titre</CardTitle></CardHeader>
          <CardContent><EChart option={byTitle} label="Répartition du portefeuille par titre" className="h-60 w-full" /></CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-base">Répartition par secteur</CardTitle></CardHeader>
          <CardContent><EChart option={bySector} label="Répartition du portefeuille par secteur" className="h-60 w-full" /></CardContent>
        </Card>
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Évolution de la valeur</CardTitle>
          <p className="text-sm text-muted-foreground">Reconstituée à partir de vos ordres et des cours de clôture.</p>
        </CardHeader>
        <CardContent>
          {history.data && history.data.length === 0
            ? <p className="py-8 text-center text-sm text-muted-foreground">Les premiers points apparaîtront après la prochaine clôture.</p>
            : <EChart option={evolution} label="Évolution de la valeur du portefeuille" className="h-72 w-full" />}
        </CardContent>
      </Card>
    </>
  );
}

function RealizedCard({ value }: { value: number }) {
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">Plus-values réalisées</CardTitle></CardHeader>
      <CardContent className="space-y-1 text-sm">
        <p className={cn("text-2xl font-semibold tabular-nums", value > 0 && "text-up", value < 0 && "text-down")}>{signed(value)}</p>
        <p className="text-muted-foreground">Gains et pertes déjà encaissés sur vos ventes, frais inclus.</p>
      </CardContent>
    </Card>
  );
}

function EmptyCard({ onAdd }: { onAdd: () => void }) {
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">Aucun ordre pour l'instant</CardTitle></CardHeader>
      <CardContent className="space-y-3 text-sm text-muted-foreground">
        <p>
          Après chaque achat ou vente chez votre courtier, recopiez l'ordre ici : {SITE_NAME} calcule votre prix de
          revient, vos plus-values et le nombre d'ordres restant pour l'année.
        </p>
        <Button onClick={onAdd}>Ajouter mon premier ordre</Button>
      </CardContent>
    </Card>
  );
}

export function PortfolioPage() {
  usePageMeta({ title: "Portefeuille", description: "Vos positions, vos plus-values et le suivi de vos ordres annuels.", noindex: true });
  const portfolio = usePortfolio();
  const orders = useOrders();
  const [dialog, setDialog] = useState<DialogState>({ open: false });
  const openNew = () => setDialog({ open: true });
  const hasOrders = (orders.data?.length ?? 0) > 0;
  const data = portfolio.data;

  return (
    <section className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Portefeuille</h1>
          <p className="mt-1 text-sm text-muted-foreground">Vos positions, vos plus-values et le suivi de vos ordres annuels.</p>
        </div>
        <Button onClick={openNew}>+ Nouvel ordre</Button>
      </header>

      {portfolio.isError && <p className="text-sm text-down">Impossible de charger le portefeuille.</p>}
      {(portfolio.isPending || orders.isPending) && <Skeleton className="h-24 w-full" />}
      {data && hasOrders && <KeyFigures data={data} />}

      <div className="grid grid-cols-1 gap-6 md:grid-cols-[1fr_2fr]">
        <OrderCounterCard />
        {orders.data && !hasOrders && <EmptyCard onAdd={openNew} />}
        {data && hasOrders && <RealizedCard value={data.realized_gain} />}
      </div>

      {data && hasOrders && data.positions.length > 0 && <Charts data={data} />}
      {data && hasOrders && (
        <Card>
          <CardHeader><CardTitle className="text-base">Positions</CardTitle></CardHeader>
          <CardContent>
            {data.positions.length > 0
              ? <PositionsTable positions={data.positions} />
              : <p className="text-sm text-muted-foreground">Toutes vos positions sont soldées.</p>}
          </CardContent>
        </Card>
      )}
      {orders.isError && <p className="text-sm text-down">Impossible de charger l'historique des ordres.</p>}
      {orders.data && hasOrders && (
        <Card>
          <CardHeader><CardTitle className="text-base">Historique des ordres</CardTitle></CardHeader>
          <CardContent><OrdersHistory orders={orders.data} onEdit={(order) => setDialog({ open: true, order })} /></CardContent>
        </Card>
      )}

      <OrderDialog open={dialog.open} order={dialog.order} onOpenChange={(open) => setDialog((d) => ({ ...d, open }))} />
    </section>
  );
}
