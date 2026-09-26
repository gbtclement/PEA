import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiGet, type NewsOut } from "@/lib/api/client";
import { formatDateTime } from "@/lib/format";

export function NewsCard({ securityId }: { securityId: number }) {
  const { data, isPending } = useQuery({
    queryKey: ["news", securityId],
    queryFn: () => apiGet<NewsOut[]>(`/api/securities/${securityId}/news`),
    staleTime: 900_000,
  });
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">Actualités récentes</CardTitle></CardHeader>
      <CardContent>
        {isPending ? <p className="text-sm text-muted-foreground">Chargement…</p> : !data?.length ? (
          <p className="text-sm text-muted-foreground">Aucune actualité récente.</p>
        ) : (
          <ul className="space-y-3">
            {data.map((item) => (
              <li key={item.url}>
                <a href={item.url} target="_blank" rel="noopener noreferrer" className="group flex items-start gap-1.5 text-sm font-medium hover:text-primary">
                  {item.title}<ExternalLink className="mt-0.5 size-3 shrink-0 opacity-50 group-hover:opacity-100" />
                </a>
                <p className="text-xs text-muted-foreground">{item.publisher ?? "Source inconnue"}{item.published_at && ` · ${formatDateTime(item.published_at)}`}</p>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
