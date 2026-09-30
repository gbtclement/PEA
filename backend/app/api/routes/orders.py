import uuid
from dataclasses import asdict, replace
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.current_user import get_current_user
from app.core.db import get_db
from app.models import Order, Security, User
from app.repositories.orders import list_orders, order_lines, to_line
from app.repositories.user_settings import get_user_settings, user_fee_grid
from app.schemas.portfolio import CounterOut, OrderIn, OrderOut
from app.services.fees import broker_fee
from app.services.market_calendar import PARIS
from app.services.portfolio import OrderLine, OversellError, compute_positions, order_counter

router = APIRouter(tags=["orders"])

NEW_ORDER_ID = 2**62  # identifiant provisoire : le nouvel ordre passe après les ordres du même jour


def paris_today() -> date:
    return datetime.now(PARIS).date()


def _out(order: Order, security: Security) -> OrderOut:
    return OrderOut(id=order.id, security_id=order.security_id, symbol=security.symbol, name=security.name,
                    trade_date=order.trade_date, side=order.side, quantity=order.quantity, unit_price=order.unit_price,
                    fee=order.fee, amount=round(order.quantity * order.unit_price, 2), note=order.note)


def _check(db: Session, lines: list[OrderLine]) -> None:
    try:
        compute_positions(lines)
    except OversellError as error:
        security = db.get(Security, error.security_id)
        name = security.name if security else "ce titre"
        raise HTTPException(status_code=422, detail=(
            f"Vente impossible : vous ne détenez que {error.held} titre(s) {name} au "
            f"{error.trade_date:%d/%m/%Y} (vente de {error.requested})."
        )) from None


def _validate(db: Session, user: User, payload: OrderIn) -> tuple[Security, float]:
    security = db.get(Security, payload.security_id)
    if security is None:
        raise HTTPException(status_code=404, detail="Titre introuvable")
    if payload.trade_date > paris_today():
        raise HTTPException(status_code=422, detail="La date de l'ordre ne peut pas être dans le futur.")
    fee = payload.fee
    if fee is None:
        fee, _ = broker_fee(payload.quantity * payload.unit_price, user_fee_grid(db, user.id))
    return security, round(fee, 2)


def _owned_or_404(db: Session, user: User, order_id: int) -> Order:
    order = db.get(Order, order_id)
    if order is None or order.user_id != user.id:
        raise HTTPException(status_code=404, detail="Ordre introuvable")
    return order


@router.get("/orders", response_model=list[OrderOut])
def get_orders(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[OrderOut]:
    return [_out(o, s) for o, s in list_orders(db, user.id)]


@router.post("/orders", response_model=OrderOut, status_code=201)
def create_order(payload: OrderIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> OrderOut:
    security, fee = _validate(db, user, payload)
    candidate = OrderLine(id=NEW_ORDER_ID, security_id=security.id, trade_date=payload.trade_date, side=payload.side,
                          quantity=payload.quantity, unit_price=payload.unit_price, fee=fee)
    _check(db, [*order_lines(db, user.id), candidate])
    order = Order(user_id=user.id, **payload.model_dump(exclude={"fee"}), fee=fee)
    db.add(order)
    db.commit()
    return _out(order, security)


@router.put("/orders/{order_id}", response_model=OrderOut)
def update_order(
    order_id: int, payload: OrderIn, db: Session = Depends(get_db), user: User = Depends(get_current_user),
) -> OrderOut:
    order = _owned_or_404(db, user, order_id)
    security, fee = _validate(db, user, payload)
    edited = replace(to_line(order), security_id=security.id, trade_date=payload.trade_date, side=payload.side,
                     quantity=payload.quantity, unit_price=payload.unit_price, fee=fee)
    _check(db, [edited if line.id == order.id else line for line in order_lines(db, user.id)])
    for key, value in payload.model_dump(exclude={"fee"}).items():
        setattr(order, key, value)
    order.fee = fee
    db.commit()
    return _out(order, security)


@router.delete("/orders/{order_id}", status_code=204)
def delete_order(order_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Response:
    order = _owned_or_404(db, user, order_id)
    _check(db, [line for line in order_lines(db, user.id) if line.id != order.id])
    db.delete(order)
    db.commit()
    return Response(status_code=204)


def counter_for(db: Session, user_id: uuid.UUID) -> CounterOut:
    settings = get_user_settings(db, user_id)
    counter = order_counter((line.trade_date for line in order_lines(db, user_id)), paris_today(),
                            settings.min_orders_per_year)
    return CounterOut(**asdict(counter), penalty_fee=settings.penalty_fee)


@router.get("/orders/counter", response_model=CounterOut)
def get_counter(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> CounterOut:
    return counter_for(db, user.id)
