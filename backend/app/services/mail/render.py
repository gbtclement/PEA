"""Rendu des mails (HTML + texte brut) à partir des modèles Jinja2. Fonctions pures."""
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape

PARIS = ZoneInfo("Europe/Paris")

SUBJECTS = {
    "verify_code": "Votre code PEA Radar : {code}",
    "welcome": "Bienvenue sur PEA Radar",
    "reset_password": "Choisir un nouveau mot de passe PEA Radar",
    "security_alert": "Alerte de sécurité sur votre compte PEA Radar",
    "new_device": "Nouvelle connexion à votre compte PEA Radar",
    "account_deleted": "Votre compte PEA Radar a été supprimé",
    "data_export_ready": "Vos données PEA Radar sont prêtes",
    "test": "Mail de test PEA Radar",
}
KINDS = frozenset(SUBJECTS)

# Phrases des alertes de sécurité (C4) ; les étapes suivantes en ajoutent.
SECURITY_EVENTS = {
    "google_linked": ("Un compte Google vient d'être associé à votre compte PEA Radar : vous pouvez maintenant vous "
                      "connecter avec Google. Si ce n'était pas vous, choisissez un nouveau mot de passe."),
    "password_reset": "Le mot de passe de votre compte vient d'être réinitialisé.",
    "admin_updated": "Un administrateur de PEA Radar vient de modifier votre compte (nom, adresse ou rôle).",
    "email_changed_by_admin": ("Un administrateur de PEA Radar vient de changer l'adresse mail de votre compte. "
                               "Les prochains mails iront à la nouvelle adresse."),
    "password_changed": ("Le mot de passe de votre compte vient d'être changé depuis les réglages. Vos autres "
                         "appareils ont été déconnectés."),
    "email_changed": ("L'adresse mail de votre compte vient d'être changée depuis les réglages. Les prochains mails "
                      "iront à la nouvelle adresse."),
    "signup_attempt": ("Quelqu'un vient d'essayer de créer un compte PEA Radar avec votre adresse. Vous avez déjà un "
                       "compte : si c'était vous, connectez-vous ou choisissez un nouveau mot de passe."),
}


@dataclass(frozen=True)
class RenderedEmail:
    subject: str
    html: str
    text: str


def _paris(value: datetime) -> str:
    return value.astimezone(PARIS).strftime("%d/%m/%Y à %H:%M")


_env = Environment(
    loader=PackageLoader("app.services.mail", "templates"),
    autoescape=select_autoescape(enabled_extensions=("html",), default_for_string=False),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)
_env.filters["paris"] = _paris


def render(kind: str, context: dict, *, base_url: str) -> RenderedEmail:
    values = {**context, "base_url": base_url.rstrip("/")}
    if kind == "security_alert":
        values["event_text"] = SECURITY_EVENTS[context["event"]]
    return RenderedEmail(
        subject=SUBJECTS[kind].format(**values),
        html=_env.get_template(f"{kind}.html").render(values),
        text=_env.get_template(f"{kind}.txt").render(values),
    )
