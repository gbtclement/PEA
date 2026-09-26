import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiSend } from "@/lib/api/client";

export function useToggleFavorite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ securityId, favorite }: { securityId: number; favorite: boolean }) =>
      apiSend(favorite ? "PUT" : "DELETE", `/api/favorites/${securityId}`),
    onSettled: () => {
      for (const key of ["screener", "top", "security"]) queryClient.invalidateQueries({ queryKey: [key] });
    },
  });
}
