import { IndicesBar } from "./IndicesBar";
import { MarketHeatmap } from "./MarketHeatmap";
import { Movers } from "./Movers";
import { TopList } from "./TopList";

export function HomePage() {
  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Accueil</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Les actions à surveiller aujourd'hui. Outil d'aide à la décision, pas un conseil en investissement.
        </p>
      </header>
      <IndicesBar />
      <div className="grid grid-cols-[2fr_1fr] gap-6">
        <TopList />
        <Movers />
      </div>
      <MarketHeatmap />
    </section>
  );
}
