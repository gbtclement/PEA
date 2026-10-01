import { useMutation, useQueryClient } from "@tanstack/react-query";
import { LogOut, Sparkles } from "lucide-react";
import { Link, useNavigate } from "react-router";
import { buttonVariants } from "@/components/ui/button";
import { useMe } from "@/features/auth/useMe";
import { apiSend } from "@/lib/api/client";
import { cn } from "@/lib/utils";

/** Bas de la barre latérale : le compte connecté, ou les liens de connexion pour un visiteur. */
export function AccountMenu() {
  const { me, isPending } = useMe();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const logout = useMutation({
    mutationFn: () => apiSend("POST", "/api/auth/logout"),
    onSuccess: () => {
      queryClient.clear();
      navigate("/");
    },
  });

  if (isPending) return null;
  if (!me) {
    return (
      <div className="flex flex-col gap-2">
        <Link to="/inscription" className={cn(buttonVariants({ size: "sm" }), "w-full")}>Créer un compte</Link>
        <Link to="/connexion" className={cn(buttonVariants({ size: "sm", variant: "outline" }), "w-full")}>Se connecter</Link>
      </div>
    );
  }
  const initials = `${me.first_name.charAt(0)}${me.last_name.charAt(0)}`.toUpperCase();
  return (
    <div className="flex items-center gap-2">
      <span aria-hidden className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
        {initials}
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{`${me.first_name} ${me.last_name}`.trim()}</p>
        <p className="truncate text-xs text-muted-foreground">{me.email}</p>
        {me.has_premium ? (
          <span className="mt-0.5 inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
            <Sparkles className="size-3" aria-hidden />Premium
          </span>
        ) : (
          <Link to="/premium" className="text-xs font-medium text-primary hover:underline">Passer Premium</Link>
        )}
      </div>
      <button type="button" aria-label="Se déconnecter" title="Se déconnecter" disabled={logout.isPending} onClick={() => logout.mutate()}
              className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground">
        <LogOut className="size-4" aria-hidden />
      </button>
    </div>
  );
}
