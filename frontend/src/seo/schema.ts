import type { SecurityDetail } from "@/lib/api/client";

export const SITE_NAME = "PEA Radar";
export const DEFAULT_DESCRIPTION =
  "Radar des actions et ETF européens éligibles au PEA : top 10 du moment, score technique et fondamental expliqué, graphiques et simulateur. Outil d'aide à la décision, pas un conseil en investissement.";

type JsonLd = Record<string, unknown>;

// En ligne, l'adresse publique est celle du navigateur : aucune configuration à tenir à jour côté frontend.
export const absoluteUrl = (path: string) => `${window.location.origin}${path.startsWith("/") ? path : `/${path}`}`;

export function breadcrumb(items: { name: string; path: string }[]): JsonLd {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((item, i) => ({ "@type": "ListItem", position: i + 1, name: item.name, item: absoluteUrl(item.path) })),
  };
}

export function webApplication(): JsonLd {
  return {
    "@context": "https://schema.org",
    "@type": "WebApplication",
    name: SITE_NAME,
    url: absoluteUrl("/"),
    description: DEFAULT_DESCRIPTION,
    applicationCategory: "FinanceApplication",
    operatingSystem: "Web",
    inLanguage: "fr-FR",
    offers: { "@type": "Offer", price: "0", priceCurrency: "EUR" },
  };
}

function securityBase(detail: SecurityDetail, type: string): JsonLd {
  return {
    "@context": "https://schema.org",
    "@type": type,
    name: detail.name,
    tickerSymbol: detail.symbol,
    ...(detail.isin && { identifier: detail.isin }),
    url: absoluteUrl(`/titres/${detail.id}`),
  };
}

export const corporation = (detail: SecurityDetail): JsonLd => ({
  ...securityBase(detail, "Corporation"),
  ...(detail.industry && { industry: detail.industry }),
});

export const investmentFund = (detail: SecurityDetail): JsonLd => securityBase(detail, "InvestmentFund");
