"""HTML des pages publiques, prêt pour les moteurs de recherche (bloc F).

Le fichier `index.html` construit par Vite reçoit : titre, description, adresse canonique, balises de partage, JSON-LD,
un résumé lisible du contenu dans `#root` (remplacé par React au démarrage) et les données de la page dans
`#cotalyx-data` (reprises par le cache des requêtes : pas d'aller-retour vers l'API au premier affichage).

Les titres et descriptions reprennent mot pour mot ceux du frontend (`usePageMeta` de chaque page) : modifier les deux
ensemble. Un test de bout en bout compare le titre servi à celui de la page chargée.
"""
import json
from dataclasses import dataclass, field
from html import escape

from app.core.brand import APP_NAME

DEFAULT_DESCRIPTION = (
    "Radar des actions et ETF : top 10 du moment, score technique et fondamental expliqué, graphiques et simulateur. "
    "Outil d'aide à la décision, pas un conseil en investissement."
)  # frontend : seo/schema.ts
LISTS = {  # frontend : app/router.tsx
    "/explorer": ("Explorer", "Toutes les actions européennes avec leur score, leurs performances et les enveloppes compatibles."),
    "/etf": ("ETF", "Les ETF, classés par score technique."),
}
STATIC_PAGES = {  # frontend : features/premium/PremiumPage.tsx, features/legal/LegalPage.tsx
    "/premium": ("Premium", f"L'assistant IA et les prévisions court terme de {APP_NAME}, en abonnement mensuel ou annuel, "
                            "résiliable à tout moment."),
    "/cgu": ("Conditions générales d'utilisation", f"Les règles d'utilisation de {APP_NAME}."),
    "/cgv": ("Conditions générales de vente", f"Les conditions de l'abonnement {APP_NAME} Premium."),
    "/confidentialite": ("Politique de confidentialité", f"Comment {APP_NAME} protège vos données personnelles."),
    "/mentions-legales": ("Mentions légales", f"Éditeur et hébergeur de {APP_NAME}."),
}


@dataclass
class PageContent:
    title: str | None  # sans le nom du site ; None pour l'accueil
    description: str
    path: str
    summary_html: str = ""
    json_ld: list[dict] = field(default_factory=list)
    data: list[tuple[list, object]] = field(default_factory=list)  # [clé de requête, données]
    noindex: bool = False
    status: int = 200

    @property
    def full_title(self) -> str:
        return f"{self.title} | {APP_NAME}" if self.title else APP_NAME


def json_for_script(value: object) -> str:
    """JSON sûr dans une balise <script> : aucun « < », « > » ou « & » brut (« </script> » ne peut pas fermer la balise)."""
    text = json.dumps(value, ensure_ascii=False)
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def head_tags(page: PageContent, base_url: str) -> str:
    url = f"{base_url}{page.path}"
    title, description = escape(page.full_title), escape(page.description)
    tags = [
        f"<title>{escape(page.full_title, quote=False)}</title>",
        f'<meta name="description" content="{description}" />',
        f'<link rel="canonical" href="{escape(url)}" />',
        '<meta property="og:type" content="website" />',
        f'<meta property="og:title" content="{title}" />',
        f'<meta property="og:description" content="{description}" />',
        f'<meta property="og:url" content="{escape(url)}" />',
        f'<meta property="og:image" content="{escape(base_url)}/og-image.png" />',
        '<meta name="twitter:card" content="summary_large_image" />',
        f'<meta name="twitter:title" content="{title}" />',
        f'<meta name="twitter:description" content="{description}" />',
    ]
    if page.noindex:
        tags.append('<meta name="robots" content="noindex, nofollow" />')
    tags += [f'<script type="application/ld+json">{json_for_script(item)}</script>' for item in page.json_ld]
    return "\n    ".join(tags)


def render_page(template: str, page: PageContent, base_url: str) -> str:
    """Remplit le gabarit : en-tête (titre et description par défaut retirés), résumé dans #root, données embarquées."""
    html = _drop_tag(template, "<title>", "</title>")
    html = _drop_tag(html, '<meta name="description"', ">")
    html = html.replace("</head>", f"  {head_tags(page, base_url)}\n  </head>", 1)
    data = f'<script id="cotalyx-data" type="application/json">{json_for_script(page.data)}</script>'
    return html.replace('<div id="root"></div>', f'<div id="root">{page.summary_html}</div>\n    {data}', 1)


def _drop_tag(html: str, start: str, end: str) -> str:
    begin = html.find(start)
    if begin == -1:
        return html
    stop = html.find(end, begin) + len(end)
    line_start = html.rfind("\n", 0, begin) + 1
    line_end = html.find("\n", stop)
    if html[line_start:begin].strip() == "" and html[stop:line_end].strip() == "":
        return html[:line_start] + html[line_end + 1:]  # balise seule sur sa ligne : la ligne entière part
    return html[:begin] + html[stop:]


def breadcrumb(base_url: str, items: list[tuple[str, str]]) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": name, "item": f"{base_url}{path}"}
                            for i, (name, path) in enumerate(items)],
    }


def web_application(base_url: str) -> dict:
    return {
        "@context": "https://schema.org", "@type": "WebApplication", "name": APP_NAME, "url": f"{base_url}/",
        "description": DEFAULT_DESCRIPTION, "applicationCategory": "FinanceApplication", "operatingSystem": "Web",
        "inLanguage": "fr-FR", "offers": {"@type": "Offer", "price": "0", "priceCurrency": "EUR"},
    }


def money(value: float | None, currency: str) -> str:
    if value is None:
        return "—"
    number = f"{value:,.2f}".replace(",", " ").replace(".", ",")
    return f"{number} {'€' if currency == 'EUR' else currency}"


def pct(value: float | None) -> str:
    return "—" if value is None else f"{value:+.2f} %".replace(".", ",")
