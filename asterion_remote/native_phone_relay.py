"""Native phone-only authenticated WSS relay.

Preserves the existing /phone/live Android backchannel and original private
pairing. It exposes NO MCP endpoint, OAuth, tool discovery, desktop route or
callable ChatGPT integration. Existing ingress may forward WSS to local 8995.
"""
from __future__ import annotations

from fastapi import FastAPI
from .native_phone_live import router as phone_router, connected

app=FastAPI(title="Asterion native phone WSS relay",
            docs_url=None, redoc_url=None, openapi_url=None)
app.include_router(phone_router)

@app.get("/healthz")
def health():
    return {"service":"asterion-native-phone-wss","ok":True,
            "phone_connected":connected()}
