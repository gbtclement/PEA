"""Export des données personnelles (spec 6.4 : accès et portabilité)."""
import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.models import (
    AiUsage, AuthSession, BillingConsent, ChatMessage, Conversation, DataExport, Favorite, NotificationPrefs, Order, PriceAlert, Security,
    Subscription, User, UserSettings,
)

EXPORT_TTL = timedelta(days=7)
ONE_PER = timedelta(days=1)
HIDDEN = {"password_hash", "token_hash", "csrf_token", "user_id"}  # jamais exportés : secrets, ou redondants


class ExportRefused(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def _plain(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


def _row(obj) -> dict:
    return {c.key: _plain(getattr(obj, c.key)) for c in inspect(obj).mapper.column_attrs if c.key not in HIDDEN}


def build_export(db: Session, user: User, now: datetime) -> dict:
    orders = db.scalars(select(Order).where(Order.user_id == user.id).order_by(Order.id)).all()
    favorites = db.scalars(select(Favorite).where(Favorite.user_id == user.id)).all()
    alerts = db.scalars(select(PriceAlert).where(PriceAlert.user_id == user.id).order_by(PriceAlert.created_at)).all()
    ids = {o.security_id for o in orders} | {f.security_id for f in favorites} | {a.security_id for a in alerts}
    securities = {s.id: {"symbol": s.symbol, "name": s.name, "isin": s.isin}
                  for s in db.scalars(select(Security).where(Security.id.in_(ids)))} if ids else {}
    settings = db.get(UserSettings, user.id)
    conversations = db.scalars(select(Conversation).where(Conversation.user_id == user.id).order_by(Conversation.id)).all()
    sub = db.get(Subscription, user.id)
    consents = db.scalars(select(BillingConsent).where(BillingConsent.user_id == user.id).order_by(BillingConsent.accepted_at)).all()
    return {
        "genere_le": now.isoformat(),
        "profil": _row(user),
        "reglages": _row(settings) if settings else None,
        "ordres": [{**_row(o), "titre": securities.get(o.security_id)} for o in orders],
        "favoris": [{**_row(f), "titre": securities.get(f.security_id)} for f in favorites],
        "notifications": _row(prefs) if (prefs := db.get(NotificationPrefs, user.id)) else None,
        "alertes_prix": [{**_row(a), "titre": securities.get(a.security_id)} for a in alerts],
        "conversations": [{**_row(c), "messages": [_row(m) for m in db.scalars(
            select(ChatMessage).where(ChatMessage.conversation_id == c.id).order_by(ChatMessage.id))]} for c in conversations],
        "usage_assistant": [_row(u) for u in db.scalars(select(AiUsage).where(AiUsage.user_id == user.id))],
        "appareils": [_row(s) for s in db.scalars(select(AuthSession).where(AuthSession.user_id == user.id))],
        "abonnement": {"formule": sub.interval, "etat": sub.status, "resiliation_demandee": sub.cancel_at_period_end,
                       "fin_de_periode": _plain(sub.current_period_end)} if sub else None,
        "accords_de_vente": [{"version_cgv": c.cgv_version, "renonciation_retractation": c.withdrawal_waiver,
                              "formule": c.interval, "accepte_le": _plain(c.accepted_at)} for c in consents],
    }


def latest_export(db: Session, user: User) -> DataExport | None:
    return db.scalar(select(DataExport).where(DataExport.user_id == user.id)
                     .order_by(DataExport.created_at.desc()).limit(1))


def request_export(db: Session, user: User, now: datetime) -> DataExport:
    """Un export à la fois, au plus un par jour (spec 6.4). Pas de commit ici."""
    last = latest_export(db, user)
    if last is not None and last.status == "pending":
        raise ExportRefused(409, "export_pending", "Votre export est déjà en préparation : vous recevrez un mail.")
    if last is not None and last.status != "failed" and last.created_at > now - ONE_PER:
        raise ExportRefused(429, "export_limit", "Un export par jour au plus : réessayez demain.")
    row = DataExport(user_id=user.id, created_at=now)
    db.add(row)
    db.flush()
    return row
