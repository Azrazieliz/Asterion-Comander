"""Real M5 Windows crawler test, including robots/SSRF failure classification."""
import json
from fastapi import HTTPException
from asterion_remote.browser_crawler import capture_public
SOURCES=["https://example.org/","https://www.iana.org/domains/reserved",
         "https://www.wikipedia.org/","https://127.0.0.1/admin"]
for url in SOURCES:
    try:
        proof=capture_public(url,2000)
        print(json.dumps({"site":url,"ok":proof["ok"],
            "http":proof["http_status"],"robots":proof["robots"],
            "hash":proof["content_sha256"],"title":proof["title"][:80],
            "captured_utc":proof["captured_utc"]}))
    except HTTPException as error:
        print(json.dumps({"site":url,"ok":False,"status":error.status_code,
            "reason":str(error.detail)[:180]}))
    except Exception as error:
        print(json.dumps({"site":url,"ok":False,"error_class":type(error).__name__}))
