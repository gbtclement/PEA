import { usePageMeta } from "@/seo/usePageMeta";
import { AssistantAdminCard } from "./AssistantAdminCard";
import { ConfigStatusCard } from "./ConfigStatusCard";
import { EnvelopeOverridesCard } from "./EnvelopeOverridesCard";
import { UsersCard } from "./UsersCard";

export function AdminPage() {
  usePageMeta({ title: "Admin", description: "Utilisateurs, assistant IA et configuration.", noindex: true });
  return (
    <section className="space-y-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Admin</h1>
          <p className="mt-1 text-sm text-muted-foreground">Utilisateurs, assistant IA et configuration du serveur.</p>
        </div>
        <a href="/documentation/" className="text-sm font-medium text-primary">Documentation admin</a>
      </header>
      <UsersCard />
      <div className="grid gap-6 lg:grid-cols-2">
        <AssistantAdminCard />
        <ConfigStatusCard />
      </div>
      <EnvelopeOverridesCard />
    </section>
  );
}
