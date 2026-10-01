import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiGet, apiSend, type NotificationPrefs, type PriceAlert } from "@/lib/api/client";
import { formatPrice } from "@/lib/format";

type Kind = Exclude<keyof NotificationPrefs, "move_threshold_pct">;

const ITEMS: { key: Kind; label: string; hint: string }[] = [
  { key: "price_move", label: "Forte variation d'un titre suivi",
    hint: "En séance : un mail quand un favori ou une position bouge d'au moins le seuil ci-dessous, une fois par titre et par jour." },
  { key: "price_alert", label: "Alertes de prix", hint: "Quand un titre franchit le seuil choisi sur sa fiche." },
  { key: "daily_recap", label: "Récap du soir",
    hint: "À 18 h 45 les jours de bourse : valeur du portefeuille, variation du jour, hausses et baisses de vos favoris." },
  { key: "weekly_recap", label: "Récap de la semaine",
    hint: "Le samedi à 9 h : performance, entrées et sorties du top 10, prévisions vérifiées." },
  { key: "order_reminder", label: "Rappel du compteur d'ordres",
    hint: "Les 1er octobre, novembre et décembre, s'il vous manque des ordres pour éviter les frais de votre banque." },
  { key: "score_change", label: "Changement de score d'un favori",
    hint: "Après la séance : entrée ou sortie du top 10, ou score qui bouge d'au moins 10 points." },
];

const unit = (currency: string) => (currency === "EUR" ? "€" : currency);
const day = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString("fr-FR") : "");

export function NotificationsCard() {
  const queryClient = useQueryClient();
  const prefs = useQuery({ queryKey: ["notifications"], queryFn: () => apiGet<NotificationPrefs>("/api/me/notifications") });
  const save = useMutation({
    mutationFn: (next: NotificationPrefs) => apiSend("PUT", "/api/me/notifications", next) as Promise<NotificationPrefs>,
    onSuccess: (data) => queryClient.setQueryData(["notifications"], data),
  });
  const data = prefs.data;
  return (
    <Card id="notifications">
      <CardHeader><CardTitle className="text-base">Notifications par mail</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        {data && (
          <ul className="divide-y divide-border">
            {ITEMS.map((item) => (
              <li key={item.key} className="flex items-start justify-between gap-4 py-2">
                <label htmlFor={`notif-${item.key}`} className="min-w-0">
                  <span className="block font-medium">{item.label}</span>
                  <span className="block text-xs text-muted-foreground">{item.hint}</span>
                </label>
                <input id={`notif-${item.key}`} type="checkbox" role="switch" className="mt-1 size-4 accent-primary"
                       checked={data[item.key]} disabled={save.isPending}
                       onChange={(e) => save.mutate({ ...data, [item.key]: e.target.checked })} />
              </li>
            ))}
          </ul>
        )}
        {data && (
          <ThresholdField key={data.move_threshold_pct} value={data.move_threshold_pct}
                          onSave={(value) => save.mutate({ ...data, move_threshold_pct: value })} />
        )}
        {save.error && <p role="alert" className="text-sm text-destructive">{save.error.message}</p>}
        <PriceAlertList />
        <p className="text-xs text-muted-foreground">Les mails liés à votre compte (codes, sécurité) sont toujours envoyés.</p>
      </CardContent>
    </Card>
  );
}

function ThresholdField({ value, onSave }: { value: number; onSave: (value: number) => void }) {
  const [text, setText] = useState(String(value).replace(".", ","));
  function commit() {
    const next = Number(text.replace(",", "."));
    if (next >= 1 && next <= 50 && next !== value) onSave(next);
    else setText(String(value).replace(".", ","));
  }
  return (
    <div className="flex items-center gap-2 text-sm">
      <label htmlFor="notif-threshold">Seuil de forte variation (%)</label>
      <Input id="notif-threshold" inputMode="decimal" className="w-20" value={text}
             onChange={(e) => setText(e.target.value)} onBlur={commit} />
    </div>
  );
}

function PriceAlertList() {
  const queryClient = useQueryClient();
  const alerts = useQuery({ queryKey: ["price-alerts"], queryFn: () => apiGet<PriceAlert[]>("/api/me/price-alerts") });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["price-alerts"] });
  const [editing, setEditing] = useState<string | null>(null);
  const rearm = useMutation({
    mutationFn: ({ id, direction, price }: { id: string; direction: string; price: number }) =>
      apiSend("PATCH", `/api/me/price-alerts/${id}`, { active: true, direction, price }),
    onSuccess: () => { setEditing(null); refresh(); },
  });
  const remove = useMutation({
    mutationFn: (alert: PriceAlert) => apiSend("DELETE", `/api/me/price-alerts/${alert.id}`), onSuccess: refresh,
  });
  const list = alerts.data ?? [];
  const error = rearm.error ?? remove.error;
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-medium">Alertes de prix</h3>
      {list.length === 0 ? (
        <p className="text-sm text-muted-foreground">Aucune alerte. Créez-en une depuis la fiche d'un titre, avec le bouton « Créer une alerte ».</p>
      ) : (
        <ul className="divide-y divide-border">
          {list.map((alert) => (
            <li key={alert.id} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 py-2 text-sm">
              <div className="min-w-0">
                <Link to={`/titres/${alert.security_id}`} className="font-medium hover:underline">{alert.name}</Link>
                <p className="text-xs text-muted-foreground">
                  {alert.direction === "above" ? "Au-dessus de" : "En dessous de"} {formatPrice(alert.price)} {unit(alert.currency)}
                  {alert.active ? " · active" : ` · déclenchée le ${day(alert.triggered_at)}`}
                </p>
              </div>
              <div className="flex gap-2">
                {!alert.active && (
                  <Button size="sm" variant="outline" aria-label={`Réarmer l'alerte sur ${alert.name}`}
                          onClick={() => { rearm.reset(); setEditing(alert.id); }}>Réarmer</Button>
                )}
                <Button size="sm" variant="outline" aria-label={`Supprimer l'alerte sur ${alert.name}`}
                        disabled={remove.isPending} onClick={() => remove.mutate(alert)}>Supprimer</Button>
              </div>
              {editing === alert.id && (
                <RearmForm alert={alert} pending={rearm.isPending} onCancel={() => setEditing(null)}
                           onSubmit={(direction, price) => rearm.mutate({ id: alert.id, direction, price })} />
              )}
            </li>
          ))}
        </ul>
      )}
      {error && <p role="alert" className="text-sm text-destructive">{error.message}</p>}
    </div>
  );
}

/** Réarmer : le cours est souvent resté près du seuil, on propose donc d'en choisir un autre. */
function RearmForm({ alert, pending, onSubmit, onCancel }: {
  alert: PriceAlert; pending: boolean; onSubmit: (direction: string, price: number) => void; onCancel: () => void;
}) {
  const [direction, setDirection] = useState(alert.direction);
  const [price, setPrice] = useState(alert.price.toFixed(2).replace(".", ","));
  function submit(event: FormEvent) {
    event.preventDefault();
    onSubmit(direction, Number(price.replace(/s/g, "").replace(",", ".")));
  }
  return (
    <form className="flex w-full flex-wrap items-end gap-2" onSubmit={submit}>
      <select aria-label="Sens" className="rounded-md border border-input bg-background px-2 py-1.5 text-sm"
              value={direction} onChange={(e) => setDirection(e.target.value)}>
        <option value="above">au-dessus de</option>
        <option value="below">en dessous de</option>
      </select>
      <label htmlFor={`rearm-${alert.id}`} className="sr-only">Nouveau prix ({unit(alert.currency)})</label>
      <Input id={`rearm-${alert.id}`} inputMode="decimal" className="w-28" value={price}
             onChange={(e) => setPrice(e.target.value)} required />
      <span className="text-xs text-muted-foreground">{unit(alert.currency)}</span>
      <Button type="submit" size="sm" disabled={pending}>Confirmer le réarmement</Button>
      <Button type="button" size="sm" variant="ghost" onClick={onCancel}>Annuler</Button>
    </form>
  );
}
