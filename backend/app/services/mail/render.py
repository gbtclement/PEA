"""Rendu des mails (HTML + texte brut) à partir des modèles Jinja2. Fonctions pures."""
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape

from app.core.brand import APP_NAME

PARIS = ZoneInfo("Europe/Paris")

SUBJECTS = {
    "verify_code": "Votre code Cotalyx : {code}",
    "welcome": "Bienvenue sur Cotalyx",
    "reset_password": "Choisir un nouveau mot de passe Cotalyx",
    "security_alert": "Alerte de sécurité sur votre compte Cotalyx",
    "new_device": "Nouvelle connexion à votre compte Cotalyx",
    "account_deleted": "Votre compte Cotalyx a été supprimé",
    "data_export_ready": "Vos données Cotalyx sont prêtes",
    "inactivity_warning": "Votre compte Cotalyx sera supprimé dans 30 jours",
    "test": "Mail de test Cotalyx",
    "price_move": "Forte variation de vos titres suivis",
    "price_alert": "Alerte de prix : {name}",
    "daily_recap": "Votre récap du soir Cotalyx",
    "weekly_recap": "Votre récap de la semaine Cotalyx",
    "order_reminder": "Compteur d'ordres : il vous manque {remaining} ordre(s)",
    "score_change": "Changement de score de vos favoris",
    "premium_started": "Bienvenue dans Cotalyx Premium",
    "payment_failed": "Le paiement de votre abonnement Premium a échoué",
    "premium_canceling": "Votre abonnement Premium est résilié",
    "premium_ended": "Votre accès Premium est terminé",
    "renewal_reminder": "Votre abonnement Premium annuel sera renouvelé le {renews_on}",
}
KINDS = frozenset(SUBJECTS)

# Phrases des alertes de sécurité (C4) ; les étapes suivantes en ajoutent.
SECURITY_EVENTS = {
    "google_linked": ("Un compte Google vient d'être associé à votre compte Cotalyx : vous pouvez maintenant vous "
                      "connecter avec Google. Si ce n'était pas vous, choisissez un nouveau mot de passe."),
    "password_reset": "Le mot de passe de votre compte vient d'être réinitialisé.",
    "admin_updated": "Un administrateur de Cotalyx vient de modifier votre compte (nom, adresse ou rôle).",
    "email_changed_by_admin": ("Un administrateur de Cotalyx vient de changer l'adresse mail de votre compte. "
                               "Les prochains mails iront à la nouvelle adresse."),
    "password_changed": ("Le mot de passe de votre compte vient d'être changé depuis les réglages. Vos autres "
                         "appareils ont été déconnectés."),
    "email_changed": ("L'adresse mail de votre compte vient d'être changée depuis les réglages. Les prochains mails "
                      "iront à la nouvelle adresse."),
    "signup_attempt": ("Quelqu'un vient d'essayer de créer un compte Cotalyx avec votre adresse. Vous avez déjà un "
                       "compte : si c'était vous, connectez-vous ou choisissez un nouveau mot de passe."),
}


@dataclass(frozen=True)
class RenderedEmail:
    subject: str
    html: str
    text: str


def _paris(value: datetime) -> str:
    return value.astimezone(PARIS).strftime("%d/%m/%Y à %H:%M")


def _number(value: float) -> str:
    return f"{value:,.2f}".replace(",", " ").replace(".", ",")


def _eur(value: float) -> str:
    return f"{_number(value)} €"


def _price(value: float, currency: str = "EUR") -> str:
    return f"{_number(value)} {'€' if currency == 'EUR' else currency}"


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{'+' if value > 0 else ''}{_number(value)} %"


def _day(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def _short(value: float) -> str:
    return f"{value:g}".replace(".", ",")


_env = Environment(
    loader=PackageLoader("app.services.mail", "templates"),
    autoescape=select_autoescape(enabled_extensions=("html",), default_for_string=False),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)
_env.filters["paris"] = _paris
_env.filters.update(eur=_eur, price=_price, pct=_pct, day=_day, short=_short)


def render(kind: str, context: dict, *, base_url: str) -> RenderedEmail:
    values = {**context, "base_url": base_url.rstrip("/"), "app_name": APP_NAME}
    if kind == "security_alert":
        values["event_text"] = SECURITY_EVENTS[context["event"]]
    return RenderedEmail(
        subject=SUBJECTS[kind].format(**values),
        html=_env.get_template(f"{kind}.html").render(values),
        text=_env.get_template(f"{kind}.txt").render(values),
    )
