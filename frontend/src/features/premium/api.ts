import { useQuery } from "@tanstack/react-query";
import { apiGet, type BillingPlans, type BillingSubscription } from "@/lib/api/client";

export const usePlans = () =>
  useQuery({ queryKey: ["billing", "plans"], queryFn: () => apiGet<BillingPlans>("/api/billing/plans"), staleTime: 3_600_000 });

export const useSubscription = (enabled = true) =>
  useQuery({ queryKey: ["billing", "subscription"], queryFn: () => apiGet<BillingSubscription>("/api/billing/subscription"), enabled });

/** Centimes → « 4,99 € ». */
export function formatAmount(cents: number, currency: string): string {
  return (cents / 100).toLocaleString("fr-FR", { style: "currency", currency: currency.toUpperCase() }).replace(/ | /g, " ");
}
