"""Request body size limit, enforced before the framework reads or spools a body.

Without it, an unauthenticated client can POST gigabytes to any endpoint: the body is read (and multipart
uploads are written to disk) before the route's authentication dependency runs. The limit checks the
declared ``Content-Length`` and also counts streamed bytes, so chunked uploads cannot dodge it. Once the
limit is exceeded the application sees a client disconnect, and whatever it answers is replaced by a 413.
"""
from __future__ import annotations

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ..config import get_settings

_BODY = b'{"detail":"Request body too large"}'


class BodyLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        s = get_settings()
        headers = {k.lower(): v for k, v in scope.get("headers", [])}
        multipart = headers.get(b"content-type", b"").lower().startswith(b"multipart/")
        limit = (s.max_upload_mb + 1) * 1024 * 1024 if multipart else s.max_json_body_kb * 1024
        declared = headers.get(b"content-length", b"")
        sent_413 = False
        exceeded = False
        received = 0

        async def reject() -> None:
            nonlocal sent_413
            if sent_413:
                return
            sent_413 = True
            await send({"type": "http.response.start", "status": 413,
                        "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(_BODY)).encode())]})
            await send({"type": "http.response.body", "body": _BODY})

        if declared.isdigit() and int(declared) > limit:
            await reject()
            return

        async def limited_receive() -> Message:
            nonlocal received, exceeded
            if exceeded:
                return {"type": "http.disconnect"}
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    exceeded = True
                    return {"type": "http.disconnect"}
            return message

        async def guarded_send(message: Message) -> None:
            if exceeded:
                await reject()  # replace whatever the application tried to answer with a 413
                return
            await send(message)

        try:
            await self.app(scope, limited_receive, guarded_send)
        except Exception:
            if not exceeded:
                raise
        if exceeded:
            await reject()
