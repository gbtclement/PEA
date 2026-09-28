import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

/** Indication seulement : la règle qui fait foi (12 caractères) est vérifiée par l'API. */
export function passwordStrength(value: string): 0 | 1 | 2 | 3 {
  if (value.length < 12) return 0;
  const kinds = [/[a-z]/, /[A-Z]/, /\d/, /[^A-Za-z0-9]/].filter((re) => re.test(value)).length;
  if (value.length >= 20) return 3;
  return kinds >= 3 ? 2 : 1;
}

const LABELS = ["Trop court (12 caractères minimum)", "Correct", "Solide", "Très solide"];
const COLORS = ["bg-red-500", "bg-amber-500", "bg-emerald-500", "bg-emerald-600"];

export function PasswordField({ id, label, value, onChange, autoComplete, showStrength = false }: {
  id: string; label: string; value: string; onChange: (value: string) => void;
  autoComplete: "new-password" | "current-password"; showStrength?: boolean;
}) {
  const [visible, setVisible] = useState(false);
  const strength = passwordStrength(value);
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="text-sm font-medium">{label}</label>
      <div className="relative">
        <Input id={id} type={visible ? "text" : "password"} value={value} autoComplete={autoComplete} required
               minLength={showStrength ? 12 : undefined} maxLength={128} className="bg-white pr-10"
               onChange={(e) => onChange(e.target.value)} />
        <button type="button" onClick={() => setVisible(!visible)} aria-label={visible ? "Masquer le mot de passe" : "Afficher le mot de passe"}
                className="absolute inset-y-0 right-0 flex w-10 items-center justify-center text-muted-foreground hover:text-foreground">
          {visible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
        </button>
      </div>
      {showStrength && value && (
        <div aria-live="polite" className="space-y-1">
          <div className="flex gap-1" aria-hidden>
            {[0, 1, 2].map((i) => <span key={i} className={cn("h-1 flex-1 rounded-full bg-muted", i < Math.max(strength, 1) && COLORS[strength])} />)}
          </div>
          <p className="text-xs text-muted-foreground">{LABELS[strength]}</p>
        </div>
      )}
    </div>
  );
}
