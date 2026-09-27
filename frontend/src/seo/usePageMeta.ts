import { useEffect } from "react";
import { useLocation } from "react-router";
import { DEFAULT_DESCRIPTION, SITE_NAME, absoluteUrl } from "./schema";

export type PageMeta = {
  /** Titre de la page, sans le nom du site ; `null` pour l'accueil (« PEA Radar » seul). */
  title: string | null;
  description: string;
  /** Adresse canonique ; par défaut, celle de la page affichée. */
  path?: string;
  /** Pages personnelles (portefeuille, assistant, réglages) ou introuvables : jamais indexées. */
  noindex?: boolean;
  jsonLd?: Record<string, unknown> | Record<string, unknown>[];
};

function upsert(tag: "meta" | "link", key: string, value: string, attrs: Record<string, string>) {
  let el = document.head.querySelector<HTMLElement>(`${tag}[${key}="${attrs[key]}"]`);
  if (!el) {
    el = document.createElement(tag);
    Object.entries(attrs).forEach(([k, v]) => el!.setAttribute(k, v));
    el.dataset.seo = "";
    document.head.appendChild(el);
  }
  el.setAttribute(tag === "link" ? "href" : "content", value);
}

const setName = (name: string, value: string) => upsert("meta", "name", value, { name });
const setProperty = (property: string, value: string) => upsert("meta", "property", value, { property });
const remove = (selector: string) => document.head.querySelectorAll(selector).forEach((el) => el.remove());

/** Met à jour les métadonnées de `<head>` pour la page affichée et les retire quand elle disparaît. */
export function usePageMeta({ title, description, path, noindex = false, jsonLd }: PageMeta) {
  const { pathname } = useLocation();
  const url = absoluteUrl(path ?? pathname);
  const fullTitle = title ? `${title} | ${SITE_NAME}` : SITE_NAME;
  const structured = JSON.stringify(jsonLd === undefined ? [] : Array.isArray(jsonLd) ? jsonLd : [jsonLd]);

  useEffect(() => {
    document.title = fullTitle;
    setName("description", description);
    upsert("link", "rel", url, { rel: "canonical" });
    setProperty("og:type", "website");
    setProperty("og:title", fullTitle);
    setProperty("og:description", description);
    setProperty("og:url", url);
    setName("twitter:card", "summary");
    setName("twitter:title", fullTitle);
    setName("twitter:description", description);
    if (noindex) setName("robots", "noindex, nofollow");
    for (const data of JSON.parse(structured) as unknown[]) {
      const script = document.createElement("script");
      script.type = "application/ld+json";
      script.dataset.seo = "";
      script.textContent = JSON.stringify(data);  // texte brut : aucune balise ne peut en sortir
      document.head.appendChild(script);
    }
    return () => {
      document.title = SITE_NAME;
      setName("description", DEFAULT_DESCRIPTION);
      remove('meta[name="robots"], script[type="application/ld+json"][data-seo], link[rel="canonical"], meta[property="og:url"]');
    };
  }, [fullTitle, description, url, noindex, structured]);
}
