import type { ReactNode } from "react";
import { Link } from "react-router";

/** Textes légaux en brouillon : les passages entre crochets sont à compléter par l'éditeur. */
export const LEGAL_UPDATED = "1er octobre 2026";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-2">
      <h2 className="text-lg font-semibold">{title}</h2>
      {children}
    </section>
  );
}

const List = ({ children }: { children: ReactNode }) => <ul className="list-disc space-y-1 pl-5">{children}</ul>;

function Table({ head, rows }: { head: [string, string]; rows: [string, string][] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr>
            {head.map((cell) => <th key={cell} className="border-b py-1.5 pr-4 text-left font-medium">{cell}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map(([a, b]) => (
            <tr key={a}>
              <td className="border-b py-1.5 pr-4 align-top">{a}</td>
              <td className="border-b py-1.5 align-top">{b}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function CGU() {
  return (
    <>
      <Section title="1. Objet">
        <p>
          PEA Radar est un outil gratuit d'aide à la décision et d'apprentissage pour le Plan d'Épargne en Actions (PEA). Les
          présentes conditions fixent les règles d'utilisation du site. Créer un compte vaut acceptation de ces conditions.
        </p>
      </Section>
      <Section title="2. Accès">
        <p>
          Le compte est réservé aux personnes de <strong>18 ans et plus</strong>. Les pages publiques (actions, prévisions, pages
          légales) restent consultables sans compte.
        </p>
      </Section>
      <Section title="3. Compte et sécurité">
        <List>
          <li>Vous vous engagez à donner des informations exactes et à les tenir à jour.</li>
          <li>Votre mot de passe est personnel : ne le partagez pas et choisissez-en un que vous n'utilisez nulle part ailleurs.</li>
          <li>
            Si vous recevez un mail pour une action que vous n'avez pas faite, cliquez sur « Ce n'était pas moi » : vos appareils
            sont déconnectés et vous pouvez choisir un nouveau mot de passe.
          </li>
        </List>
      </Section>
      <Section title="4. Pas un conseil en investissement">
        <p>
          PEA Radar n'est <strong>pas un conseil en investissement</strong> et ne fournit aucune recommandation personnalisée au
          sens de l'Autorité des marchés financiers (AMF).
        </p>
        <List>
          <li>Les cours sont différés et peuvent être incomplets ou inexacts.</li>
          <li>L'éligibilité au PEA est déduite automatiquement : elle peut être erronée.</li>
          <li>Les scores et les prévisions sont des calculs sans aucune garantie de résultat.</li>
          <li>Vérifiez toujours auprès de votre banque avant de passer un ordre. Investir comporte un risque de perte en capital.</li>
        </List>
      </Section>
      <Section title="5. Assistant IA">
        <p>
          L'assistant est réservé aux comptes Premium. Ses réponses sont générées par Claude, un modèle d'intelligence
          artificielle de la société Anthropic : elles peuvent être fausses ou incomplètes et ne remplacent pas votre propre
          vérification. Son utilisation est soumise à une limite mensuelle.
        </p>
      </Section>
      <Section title="6. Premium">
        <p>
          Le statut Premium est aujourd'hui activé par l'administrateur. Un abonnement payant, s'il est proposé, fera l'objet de
          conditions générales de vente (CGV) distinctes.
        </p>
      </Section>
      <Section title="7. Suspension et suppression">
        <List>
          <li>Vous pouvez supprimer votre compte à tout moment depuis les Réglages.</li>
          <li>L'éditeur peut suspendre ou supprimer un compte en cas d'abus ou de non-respect de ces conditions.</li>
          <li>Un compte inutilisé pendant 3 ans est supprimé, après un mail de prévenance envoyé 30 jours avant.</li>
        </List>
      </Section>
      <Section title="8. Responsabilité">
        <p>
          Le service est fourni tel quel, sans garantie de disponibilité continue. La responsabilité de l'éditeur est limitée
          aux dommages directs prouvés ; il ne répond pas des décisions d'investissement prises à partir du site.
        </p>
      </Section>
      <Section title="9. Modification des conditions">
        <p>
          Ces conditions peuvent évoluer. En cas de changement, une nouvelle acceptation vous est demandée à votre prochaine
          visite.
        </p>
      </Section>
      <Section title="10. Droit applicable et contact">
        <p>
          Ces conditions sont soumises au droit français. En cas de litige, et à défaut d'accord amiable, les tribunaux de
          [À COMPLÉTER : ville] sont compétents.
        </p>
        <p>Contact : [À COMPLÉTER : adresse de contact].</p>
      </Section>
    </>
  );
}

export function PRIVACY() {
  return (
    <>
      <Section title="Responsable du traitement">
        <p>[À COMPLÉTER : nom ou société, adresse].</p>
      </Section>
      <Section title="Données collectées">
        <List>
          <li>Compte : prénom, nom, adresse mail, mot de passe (enregistré uniquement sous forme hachée).</li>
          <li>Données que vous saisissez : ordres, favoris, réglages, conversations avec l'assistant.</li>
          <li>Données techniques : appareils connectés, adresse IP tronquée, journal de sécurité, historique des mails envoyés.</li>
        </List>
      </Section>
      <Section title="Finalités et bases légales">
        <Table head={["Finalité", "Base légale"]} rows={[
          ["Fournir le service (compte, portefeuille, assistant)", "Exécution du contrat (CGU)"],
          ["Sécurité et prévention des abus", "Intérêt légitime"],
          ["Mails liés au compte (validation, alertes de sécurité)", "Exécution du contrat (CGU)"],
        ]} />
      </Section>
      <Section title="Durées de conservation">
        <Table head={["Donnée", "Durée"]} rows={[
          ["Compte et données saisies", "Jusqu'à la suppression du compte, ou 3 ans sans connexion (mail de prévenance 30 jours avant)"],
          ["Compte dont l'adresse n'a pas été validée", "7 jours"],
          ["Export de vos données", "7 jours"],
          ["Historique des mails envoyés", "90 jours"],
          ["Journal de sécurité", "12 mois"],
        ]} />
      </Section>
      <Section title="Sous-traitants">
        <List>
          <li>Hébergeur : [À COMPLÉTER].</li>
          <li><strong>Brevo</strong> : envoi des mails.</li>
          <li><strong>Google</strong> : connexion avec Google, uniquement pour ceux qui l'utilisent.</li>
          <li><strong>Cloudflare</strong> (Turnstile) : protection contre les robots sur les formulaires.</li>
          <li><strong>Anthropic</strong> : assistant IA ; vos questions y sont envoyées pour produire les réponses, aux États-Unis.</li>
        </List>
      </Section>
      <Section title="Transferts hors de l'Union européenne">
        <p>
          Anthropic, Google et Cloudflare peuvent traiter des données aux États-Unis. Ces transferts sont encadrés par les
          clauses contractuelles types de la Commission européenne ou le cadre de protection des données UE–États-Unis
          [À VÉRIFIER].
        </p>
      </Section>
      <Section title="Vos droits">
        <List>
          <li>Accès et portabilité : bouton <strong>Exporter mes données</strong> dans les <Link className="underline" to="/reglages">Réglages</Link>.</li>
          <li>Rectification : modifiez vos informations dans les Réglages.</li>
          <li>Effacement : bouton <strong>Supprimer mon compte</strong> dans les Réglages.</li>
          <li>Opposition et autres demandes : écrivez au contact indiqué dans les mentions légales.</li>
          <li>
            Réclamation : vous pouvez saisir la CNIL (<a className="underline" href="https://www.cnil.fr" rel="noreferrer" target="_blank">cnil.fr</a>).
          </li>
        </List>
      </Section>
      <Section title="Cookies">
        <p>
          PEA Radar n'utilise que des cookies strictement nécessaires : <code>pea_session</code> (connexion),{" "}
          <code>pea_csrf</code> (protection des formulaires), <code>pea_device</code> (reconnaître un appareil déjà utilisé) et
          ceux de Turnstile (anti-robots). Aucun cookie de publicité ni de mesure d'audience : c'est pourquoi il n'y a pas de
          bandeau.
        </p>
      </Section>
    </>
  );
}

export function NOTICE() {
  return (
    <>
      <Section title="Éditeur">
        <p>[À COMPLÉTER : nom, statut, SIRET éventuel, adresse, contact].</p>
      </Section>
      <Section title="Directeur de la publication">
        <p>[À COMPLÉTER].</p>
      </Section>
      <Section title="Hébergeur">
        <p>[À COMPLÉTER : nom, adresse, téléphone].</p>
      </Section>
      <Section title="Propriété intellectuelle">
        <p>
          Les textes, le code et la présentation de PEA Radar sont protégés. Les marques et noms de sociétés cités appartiennent
          à leurs propriétaires respectifs.
        </p>
      </Section>
      <Section title="Données de marché">
        <p>
          Les cours et informations financières proviennent de Yahoo Finance et d'Euronext. Ils sont différés et fournis sans
          garantie d'exactitude ni d'exhaustivité.
        </p>
      </Section>
    </>
  );
}
