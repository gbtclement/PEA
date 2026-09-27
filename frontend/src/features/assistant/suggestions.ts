export const SECURITY_SUGGESTIONS = [
  "Analyse cette action",
  "Pourquoi est-elle dans le top 10 ?",
  "Aurais-je dû l'acheter il y a une semaine ?",
  "Quels sont les risques ?",
];

export const GENERAL_SUGGESTIONS = [
  "Analyse mon portefeuille",
  "Explique-moi le top 10 du moment",
  "Combien d'ordres me reste-t-il à passer cette année ?",
  "C'est quoi le PER, simplement ?",
];

/** Libellés des outils pour les messages enregistrés (mêmes textes que côté serveur). */
export const TOOL_NAMES: Record<string, string> = {
  search_securities: "Recherche de titres",
  get_security_overview: "Fiche du titre",
  get_price_history: "Historique des cours",
  get_top10: "Top 10",
  get_portfolio: "Votre portefeuille",
  simulate_past_investment: "Simulation d'achat passé",
  web_search: "Recherche web",
};
