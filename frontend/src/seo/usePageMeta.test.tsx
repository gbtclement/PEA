import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import type { SecurityDetail } from "@/lib/api/client";
import { breadcrumb, corporation, investmentFund } from "./schema";
import { usePageMeta, type PageMeta } from "./usePageMeta";

function Page(meta: PageMeta) {
  usePageMeta(meta);
  return null;
}

const renderAt = (meta: PageMeta, path = "/explorer") =>
  render(<MemoryRouter initialEntries={[path]}><Page {...meta} /></MemoryRouter>);

const head = (selector: string) => document.head.querySelector(selector);
const content = (selector: string) => head(selector)?.getAttribute("content");
const jsonLd = () => document.head.querySelectorAll('script[type="application/ld+json"]');

test("titre, description, canonical et Open Graph absolus", () => {
  renderAt({ title: "Explorer", description: "Toutes les actions." });
  expect(document.title).toBe("Explorer | PEA Radar");
  expect(content('meta[name="description"]')).toBe("Toutes les actions.");
  expect(head('link[rel="canonical"]')?.getAttribute("href")).toBe(`${window.location.origin}/explorer`);
  expect(content('meta[property="og:url"]')).toBe(`${window.location.origin}/explorer`);
  expect(content('meta[property="og:title"]')).toBe("Explorer | PEA Radar");
  expect(content('meta[property="og:description"]')).toBe("Toutes les actions.");
  expect(content('meta[name="twitter:card"]')).toBe("summary");
  expect(content('meta[name="twitter:title"]')).toBe("Explorer | PEA Radar");
});

test("accueil : titre seul du site", () => {
  renderAt({ title: null, description: "Radar PEA." }, "/");
  expect(document.title).toBe("PEA Radar");
  expect(head('link[rel="canonical"]')?.getAttribute("href")).toBe(`${window.location.origin}/`);
});

test("noindex ajouté puis retiré quand la page change", () => {
  const view = renderAt({ title: "Portefeuille", description: "Privé.", noindex: true }, "/portefeuille");
  expect(content('meta[name="robots"]')).toBe("noindex, nofollow");
  view.rerender(<MemoryRouter initialEntries={["/explorer"]}><Page title="Explorer" description="Public." /></MemoryRouter>);
  expect(head('meta[name="robots"]')).toBeNull();
});

test("JSON-LD inséré comme texte, sans balise injectée", () => {
  const data = { "@context": "https://schema.org", "@type": "Corporation", name: "Evil </script><img src=x>" };
  renderAt({ title: "X", description: "Y", jsonLd: data });
  const scripts = jsonLd();
  expect(scripts).toHaveLength(1);
  expect(JSON.parse(scripts[0].textContent!)).toEqual(data);
  expect(scripts[0].children).toHaveLength(0);
  expect(document.head.querySelector("img")).toBeNull();
});

test("plusieurs blocs JSON-LD, tous retirés au démontage avec le noindex", () => {
  const view = renderAt({ title: "X", description: "Y", noindex: true, jsonLd: [{ a: 1 }, { b: 2 }] });
  expect(jsonLd()).toHaveLength(2);
  view.unmount();
  expect(jsonLd()).toHaveLength(0);
  expect(head('meta[name="robots"]')).toBeNull();
  expect(document.title).toBe("PEA Radar");
});

const DETAIL = {
  id: 7, name: "LVMH", symbol: "MC", isin: "FR0000121014", market: "Euronext Paris", kind: "stock",
  sector: "Consumer Cyclical", industry: "Luxury Goods", currency: "EUR", price: 612.3,
} as unknown as SecurityDetail;

test("Corporation avec tickerSymbol, ISIN et adresse de la fiche", () => {
  const data = corporation(DETAIL);
  expect(data).toMatchObject({
    "@context": "https://schema.org", "@type": "Corporation", name: "LVMH", tickerSymbol: "MC",
    identifier: "FR0000121014", url: `${window.location.origin}/titres/7`,
  });
});

test("InvestmentFund pour un ETF", () => {
  const data = investmentFund({ ...DETAIL, name: "Amundi MSCI World", symbol: "CW8", kind: "etf" } as SecurityDetail);
  expect(data).toMatchObject({ "@type": "InvestmentFund", name: "Amundi MSCI World", tickerSymbol: "CW8" });
});

test("BreadcrumbList numérotée avec adresses absolues", () => {
  expect(breadcrumb([{ name: "Accueil", path: "/" }, { name: "Explorer", path: "/explorer" }])).toEqual({
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Accueil", item: `${window.location.origin}/` },
      { "@type": "ListItem", position: 2, name: "Explorer", item: `${window.location.origin}/explorer` },
    ],
  });
});
