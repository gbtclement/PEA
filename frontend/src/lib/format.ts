const number2 = new Intl.NumberFormat("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const dateTime = new Intl.DateTimeFormat("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });

export function formatPrice(value: number | null | undefined): string {
  return value == null ? "—" : number2.format(value);
}

export function formatPct(value: number | null | undefined): string {
  if (value == null) return "—";
  return `${value > 0 ? "+" : ""}${number2.format(value)} %`;
}

export function formatDateTime(iso: string | null | undefined): string {
  return iso ? dateTime.format(new Date(iso)) : "—";
}

const compact = new Intl.NumberFormat("fr-FR", { notation: "compact", maximumFractionDigits: 1 });

export function formatNumber(value: number | null | undefined, digits = 2): string {
  return value == null ? "—" : new Intl.NumberFormat("fr-FR", { maximumFractionDigits: digits }).format(value);
}

export function formatRatioPct(fraction: number | null | undefined): string {
  return fraction == null ? "—" : `${number2.format(fraction * 100)} %`;
}

export function formatCompactEur(value: number | null | undefined): string {
  return value == null ? "—" : `${compact.format(value)} €`;
}

export function formatDate(isoDate: string | null | undefined): string {
  if (!isoDate) return "—";
  const [year, month, day] = isoDate.slice(0, 10).split("-");
  return `${day}/${month}/${year}`;
}
