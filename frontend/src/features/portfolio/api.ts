import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiSend, type CounterOut, type HistoryPointOut, type OrderIn, type OrderOut, type PortfolioOut } from "@/lib/api/client";

const PORTFOLIO_KEYS = [["portfolio"], ["portfolio-history"], ["orders"], ["order-counter"]];

export function usePortfolio() {
  return useQuery({ queryKey: ["portfolio"], queryFn: () => apiGet<PortfolioOut>("/api/portfolio"), refetchInterval: 60_000 });
}

export function usePortfolioHistory() {
  return useQuery({ queryKey: ["portfolio-history"], queryFn: () => apiGet<HistoryPointOut[]>("/api/portfolio/history") });
}

export function useOrders() {
  return useQuery({ queryKey: ["orders"], queryFn: () => apiGet<OrderOut[]>("/api/orders") });
}

export function useOrderCounter() {
  return useQuery({ queryKey: ["order-counter"], queryFn: () => apiGet<CounterOut>("/api/orders/counter") });
}

function useInvalidatePortfolio() {
  const queryClient = useQueryClient();
  return () => {
    for (const queryKey of PORTFOLIO_KEYS) queryClient.invalidateQueries({ queryKey });
  };
}

export function useSaveOrder() {
  const invalidate = useInvalidatePortfolio();
  return useMutation({
    mutationFn: ({ id, order }: { id?: number; order: OrderIn }) =>
      apiSend(id ? "PUT" : "POST", id ? `/api/orders/${id}` : "/api/orders", order) as Promise<OrderOut>,
    onSuccess: invalidate,
  });
}

export function useDeleteOrder() {
  const invalidate = useInvalidatePortfolio();
  return useMutation({ mutationFn: (id: number) => apiSend("DELETE", `/api/orders/${id}`), onSuccess: invalidate });
}
