import { usePageMeta } from "@/seo/usePageMeta";
import { DataCard } from "./DataCard";
import { DevicesCard } from "./DevicesCard";
import { EmailCard } from "./EmailCard";
import { FeeSettingsCard } from "./FeeSettingsCard";
import { NotificationsCard } from "./NotificationsCard";
import { PasswordCard } from "./PasswordCard";
import { ProfileCard } from "./ProfileCard";
import { SubscriptionCard } from "./SubscriptionCard";

export function SettingsPage() {
  usePageMeta({ title: "Réglages", description: "Votre profil, votre abonnement, vos appareils, vos notifications et les frais de votre courtier.", noindex: true });
  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Réglages</h1>
        <p className="mt-1 text-sm text-muted-foreground">Votre profil, votre abonnement, vos appareils, vos notifications et les frais de votre courtier.</p>
      </header>
      <ProfileCard />
      <SubscriptionCard />
      <PasswordCard />
      <EmailCard />
      <DevicesCard />
      <DataCard />
      <NotificationsCard />
      <FeeSettingsCard />
    </section>
  );
}
