import { useCallback, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router";
import { EChart } from "@/components/charts/EChart";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiGet, type HeatmapItem } from "@/lib/api/client";
import { buildHeatmapOption } from "./heatmapOption";

export function MarketHeatmap() {
  const navigate = useNavigate();
  const { data } = useQuery({ queryKey: ["heatmap"], queryFn: () => apiGet<HeatmapItem[]>("/api/market/heatmap"), refetchInterval: 120_000 });
  const option = useMemo(() => buildHeatmapOption(data ?? []), [data]);
  const onItemClick = useCallback((item: unknown) => {
    const id = (item as { id?: number } | undefined)?.id;
    if (id) navigate(`/titres/${id}`);
  }, [navigate]);
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Carte du marché</CardTitle>
        <p className="text-sm text-muted-foreground">Taille = capitalisation · couleur = variation du jour. Cliquez sur une case pour ouvrir la fiche.</p>
      </CardHeader>
      <CardContent>
        <EChart option={option} label="Carte du marché : actions colorées selon leur variation du jour" onItemClick={onItemClick} className="h-[420px] w-full" />
      </CardContent>
    </Card>
  );
}
