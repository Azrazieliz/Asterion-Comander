"""Local-only bearer authentication for Asterion Remote."""
import hmac
import os
from fastapi import Header, HTTPException


def configured_token() -> str:
    token = os.environ.get('ASTERION_API_TOKEN', '')
    if len(token) < 32:
        raise RuntimeError('Set ASTERION_API_TOKEN to a randomly generated secret (32+ characters)')
    return token


def require_token(authorization: str | None = Header(default=None)) -> None:
    supplied = (authorization or '')
    supplied = supplied[7:] if supplied.startswith('Bearer ') else ''
    if not hmac.compare_digest(supplied.encode(), configured_token().encode()):
        raise HTTPException(status_code=401, detail='Bearer token required',
                            headers={'WWW-Authenticate': 'Bearer'})
