import { usePageMeta } from "@/seo/usePageMeta";
import { DataCard } from "./DataCard";
import { DevicesCard } from "./DevicesCard";
import { EmailCard } from "./EmailCard";
import { FeeSettingsCard } from "./FeeSettingsCard";
import { PasswordCard } from "./PasswordCard";
import { ProfileCard } from "./ProfileCard";

export function SettingsPage() {
  usePageMeta({ title: "Réglages", description: "Votre profil, vos appareils et les frais de votre caisse régionale.", noindex: true });
  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Réglages</h1>
        <p className="mt-1 text-sm text-muted-foreground">Votre profil, vos appareils connectés et les frais de votre caisse régionale.</p>
      </header>
      <ProfileCard />
      <PasswordCard />
      <EmailCard />
      <DevicesCard />
      <DataCard />
      <FeeSettingsCard />
    </section>
  );
}
