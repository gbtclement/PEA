"""Cache HTTP des réponses publiques (bloc F).

Une route publique déclare `dependencies=[Depends(public_cache(60))]` : sans session, la réponse est réutilisable
60 s par le navigateur et les intermédiaires (`Vary: Cookie`) ; avec une session (favoris, enveloppes du membre),
elle n'est gardée nulle part. `ETagMiddleware` ajoute une empreinte aux réponses publiques et répond 304 quand le
navigateur a déjà la même.
"""
import hashlib
from collections.abc import Callable

from fastapi import Request, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.services.auth.sessions import SESSION_COOKIE

PRIVATE = "private, no-store"


def cache_control(request: Request, seconds: int) -> dict[str, str]:
    if request.cookies.get(SESSION_COOKIE):
        return {"Cache-Control": PRIVATE}
    return {"Cache-Control": f"public, max-age={seconds}", "Vary": "Cookie"}


def public_cache(seconds: int) -> Callable[[Request, Response], None]:
    def apply(request: Request, response: Response) -> None:
        response.headers.update(cache_control(request, seconds))
    return apply


class ETagMiddleware:
    """Empreinte faible (W/"…") sur les réponses GET publiques ; 304 si « If-None-Match » correspond."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] != "GET":
            await self.app(scope, receive, send)
            return
        start: Message | None = None
        chunks: list[bytes] = []

        async def capture(message: Message) -> None:
            nonlocal start
            if message["type"] == "http.response.start":
                headers = dict(message.get("headers", []))
                if not headers.get(b"cache-control", b"").startswith(b"public"):
                    start = None
                    await send(message)  # pas publique (ou flux SSE) : rien n'est retenu
                    return
                start = message
                return
            if start is None:
                await send(message)
                return
            chunks.append(message.get("body", b""))
            if message.get("more_body"):
                return
            body = b"".join(chunks)
            etag = f'W/"{hashlib.sha256(body).hexdigest()[:32]}"'.encode()
            request_headers = dict(scope.get("headers", []))
            headers = [(k, v) for k, v in start["headers"] if k != b"content-length"]
            headers.append((b"etag", etag))
            if request_headers.get(b"if-none-match") == etag:
                await send({**start, "status": 304, "headers": headers})
                await send({"type": "http.response.body", "body": b""})
                return
            headers.append((b"content-length", str(len(body)).encode()))
            await send({**start, "headers": headers})
            await send({"type": "http.response.body", "body": body})

        await self.app(scope, receive, capture)
