"""Owner-authenticated Shared Browser entry point for Asterion apps.

The shared fetcher is intentionally not a media download service. It supplies
source URL, text and links with integrity receipts. No implicit AI actions.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel,Field

from .security import require_token
from .control_v2_routes import _owner_approval
from . import shared_browser

router=APIRouter(prefix="/api/v1/intelligence/browser",
                 dependencies=[Depends(require_token)])


class OpenPage(BaseModel):
    url:str=Field(min_length=8,max_length=2048)
    tor:bool=False
    timeout_s:float=Field(default=9,ge=1,le=20)


@router.get("/status")
def browser_status():
    import os
    return {"ok":True,"shared_browser_available":True,
            "public_html_research":True,
            "server_side_javascript_execution":False,
            "tor_socks5_configured":os.getenv("ASTERION_TOR_ENABLED","0")=="1",
            "tor_network_connected":False,
            "full_website_ui_rendering":False,
            "rounder_or_downloader_reimplemented":False}


@router.post("/open")
def browser_open(body:OpenPage,
                 x_owner_approval:str|None=Header(default=None)):
    _owner_approval(x_owner_approval)
    try:
        return shared_browser.fetch(body.url,tor=body.tor,
                                    timeout_s=body.timeout_s)
    except PermissionError as exc:
        raise HTTPException(403,type(exc).__name__) from exc
    except (ValueError,RuntimeError) as exc:
        raise HTTPException(422,type(exc).__name__) from exc
    except (OSError,TimeoutError) as exc:
        raise HTTPException(502,"Website unavailable: "+type(exc).__name__) from exc
