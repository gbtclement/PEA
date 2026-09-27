import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiSend, type AssistantSettingsOut, type ConversationDetail, type ConversationOut } from "@/lib/api/client";

export const useAssistantSettings = () =>
  useQuery({ queryKey: ["assistant-settings"], queryFn: () => apiGet<AssistantSettingsOut>("/api/assistant/settings") });

export const useConversations = () =>
  useQuery({ queryKey: ["conversations"], queryFn: () => apiGet<ConversationOut[]>("/api/assistant/conversations") });

export const useConversation = (id: number | null) =>
  useQuery({
    queryKey: ["conversation", id],
    queryFn: () => apiGet<ConversationDetail>(`/api/assistant/conversations/${id}`),
    enabled: id !== null,
  });

export const createConversation = (securityId?: number) =>
  apiSend("POST", "/api/assistant/conversations", { security_id: securityId ?? null }) as Promise<ConversationOut>;

export function useDeleteConversation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiSend("DELETE", `/api/assistant/conversations/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["conversations"] }),
  });
}
