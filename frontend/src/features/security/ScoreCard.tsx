import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScoreGauge } from "@/components/ScoreGauge";
import type { SecurityDetail } from "@/lib/api/client";
import { formatNumber } from "@/lib/format";

function exclusionReason(detail: SecurityDetail): string {
  const score = detail.score_detail!;
  if (!score.liquid) return "titre peu échangé";
  if (score.history_days < 200) return "historique trop court";
  if (detail.eligibility !== "eligible") return "éligibilité PEA non confirmée";
  return "données insuffisantes";
}

export function ScoreCard({ detail }: { detail: SecurityDetail }) {
  const score = detail.score_detail;
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">Score mixte</CardTitle></CardHeader>
      <CardContent>
        {!score || score.total == null ? (
          <p className="text-sm text-muted-foreground">Score pas encore calculé (historique ou données insuffisants).</p>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center gap-4">
              <ScoreGauge score={score.total} size={64} />
              <div className="text-sm">
                <p>Technique : <strong>{formatNumber(score.technical, 0)}</strong>/100 · Fondamental : <strong>{formatNumber(score.fundamental, 0)}</strong>/100</p>
                {score.available_ratio < 1 && <p className="text-amber-700">Données incomplètes : score calculé sur {Math.round(score.available_ratio * 100)} % des critères.</p>}
                {!score.eligible_for_top && detail.kind === "stock" && (
                  <p className="text-muted-foreground">Hors top 10 : {exclusionReason(detail)}.</p>
                )}
              </div>
            </div>
            <ul className="space-y-2.5">
              {score.components.map((c) => (
                <li key={c.key}>
                  <div className="flex justify-between gap-3 text-sm"><span>{c.message}</span><span className="shrink-0 text-muted-foreground">{formatNumber(c.points, 1)}/{formatNumber(c.max_points, 1)}</span></div>
                  <div className="mt-1 h-1.5 rounded-full bg-muted">
                    <div className="h-1.5 rounded-full bg-primary" style={{ width: `${(c.points / c.max_points) * 100}%` }} />
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
