import type { ReactNode } from "react";
import { Link } from "react-router";

/** Textes légaux en brouillon : les passages entre crochets sont à compléter par l'éditeur. */
export const LEGAL_UPDATED = "5 octobre 2026";

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
          PEA Radar est un outil d'aide à la décision et d'apprentissage pour le Plan d'Épargne en Actions (PEA). L'essentiel du
          site est gratuit ; l'assistant IA et la liste des prévisions font partie d'un abonnement payant, Premium. Les présentes
          conditions fixent les règles d'utilisation du site. Créer un compte vaut acceptation de ces conditions.
        </p>
      </Section>
      <Section title="2. Accès">
        <p>
          Le compte est réservé aux personnes de <strong>18 ans et plus</strong>. Les pages publiques (actions, ETF, pages légales,
          présentation de Premium) restent consultables sans compte.
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
          Premium donne accès à l'assistant IA et à la liste des prévisions court terme. Il s'obtient par un abonnement payant,
          mensuel ou annuel, régi par les <Link className="underline" to="/cgv">conditions générales de vente</Link>. L'éditeur peut
          aussi l'offrir à certains comptes.
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

export function CGV() {
  return (
    <>
      <Section title="1. Vendeur">
        <p>[À COMPLÉTER : nom ou société, statut, SIRET, adresse, adresse de contact].</p>
      </Section>
      <Section title="2. Objet">
        <p>
          Ces conditions régissent l'abonnement <strong>PEA Radar Premium</strong>, qui donne accès à l'assistant IA et à la liste
          des prévisions court terme, pour un utilisateur disposant d'un compte PEA Radar. Le reste du site reste régi par les{" "}
          <Link className="underline" to="/cgu">CGU</Link>.
        </p>
      </Section>
      <Section title="3. Prix et paiement">
        <List>
          <li>Les prix sont affichés sur la page <Link className="underline" to="/premium">Premium</Link>, en euros toutes taxes comprises. [À VÉRIFIER : mention « TVA non applicable, article 293 B du CGI » si le vendeur est en franchise de TVA.]</li>
          <li>Le paiement se fait par carte bancaire via Stripe, au début de chaque période (mois ou année). PEA Radar ne voit jamais les données de carte.</li>
          <li>Les factures sont disponibles depuis « Gérer mon abonnement », dans les Réglages.</li>
        </List>
      </Section>
      <Section title="4. Durée et renouvellement">
        <p>
          L'abonnement est conclu pour un mois ou un an et se renouvelle automatiquement pour la même durée. Pour la formule annuelle,
          un mail rappelle la date et le prix du renouvellement au moins 30 jours avant.
        </p>
      </Section>
      <Section title="5. Résiliation">
        <p>
          L'abonné peut résilier à tout moment depuis « Gérer mon abonnement ». La résiliation est effective à la fin de la période
          déjà payée : l'accès Premium continue jusque-là, sans remboursement au prorata. La suppression du compte met fin à
          l'abonnement immédiatement, sans remboursement de la période en cours.
        </p>
      </Section>
      <Section title="6. Droit de rétractation">
        <p>
          Premium est un service fourni dès la souscription. Avant de payer, l'abonné demande l'accès immédiat et renonce
          expressément à son droit de rétractation de 14 jours (article L221-28 du Code de la consommation), en cochant une case
          prévue à cet effet.
        </p>
      </Section>
      <Section title="7. Impayés">
        <p>
          En cas d'échec de paiement, Stripe réessaie pendant quelques jours et l'accès continue. Sans paiement au terme de ces
          tentatives, l'abonnement prend fin et l'accès Premium est retiré.
        </p>
      </Section>
      <Section title="8. Service">
        <List>
          <li>PEA Radar n'est <strong>pas un conseil en investissement</strong> : l'assistant et les prévisions sont des outils d'aide à la décision, sans garantie de résultat.</li>
          <li>L'assistant IA est soumis à une limite d'utilisation mensuelle.</li>
          <li>Le service peut évoluer (méthodes de prévision, modèle d'IA) et être interrompu pour maintenance.</li>
        </List>
      </Section>
      <Section title="9. Médiation et litiges">
        <p>
          En cas de litige, l'abonné peut recourir gratuitement au médiateur de la consommation : [À COMPLÉTER : nom et site du
          médiateur]. Ces conditions sont soumises au droit français.
        </p>
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
          <li>Données que vous saisissez : ordres, favoris, réglages, préférences de notification, alertes de prix, conversations avec l'assistant.</li>
          <li>Données techniques : appareils connectés, adresse IP tronquée, journal de sécurité, historique des mails envoyés.</li>
          <li>Abonnement : formule, état et dates de l'abonnement Premium, et la preuve de vos accords avant paiement (version des CGV, date, renonciation au droit de rétractation). PEA Radar ne voit jamais votre numéro de carte : le paiement est traité par Stripe.</li>
        </List>
      </Section>
      <Section title="Finalités et bases légales">
        <Table head={["Finalité", "Base légale"]} rows={[
          ["Fournir le service (compte, portefeuille, assistant)", "Exécution du contrat (CGU)"],
          ["Sécurité et prévention des abus", "Intérêt légitime"],
          ["Mails liés au compte (validation, alertes de sécurité)", "Exécution du contrat (CGU)"],
          ["Notifications par mail que vous avez choisies", "Exécution du contrat (désactivables à tout moment)"],
          ["Abonnement Premium et facturation", "Exécution du contrat (CGV) ; obligation légale pour les factures"],
        ]} />
      </Section>
      <Section title="Durées de conservation">
        <Table head={["Donnée", "Durée"]} rows={[
          ["Compte et données saisies", "Jusqu'à la suppression du compte, ou 3 ans sans connexion (mail de prévenance 30 jours avant)"],
          ["Compte dont l'adresse n'a pas été validée", "7 jours"],
          ["Export de vos données", "7 jours"],
          ["Historique des mails envoyés", "90 jours"],
          ["Journal de sécurité", "12 mois"],
          ["Abonnement et accords de vente", "Jusqu'à la suppression du compte"],
          ["Factures (chez Stripe)", "10 ans (obligation comptable)"],
        ]} />
      </Section>
      <Section title="Sous-traitants">
        <List>
          <li>Hébergeur : [À COMPLÉTER].</li>
          <li><strong>Brevo</strong> : envoi des mails.</li>
          <li><strong>Google</strong> : connexion avec Google, uniquement pour ceux qui l'utilisent.</li>
          <li><strong>Cloudflare</strong> (Turnstile) : protection contre les robots sur les formulaires.</li>
          <li><strong>Anthropic</strong> : assistant IA ; vos questions y sont envoyées pour produire les réponses, aux États-Unis.</li>
          <li><strong>Stripe</strong> (Stripe Payments Europe, Irlande) : paiement de l'abonnement et factures.</li>
        </List>
      </Section>
      <Section title="Transferts hors de l'Union européenne">
        <p>
          Anthropic, Google, Cloudflare et Stripe peuvent traiter des données aux États-Unis. Ces transferts sont encadrés par les
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
