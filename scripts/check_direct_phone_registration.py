"""Verify Android-owned credential can authenticate direct MCP; never print key."""
from asterion_remote.phone_bridge import load
from asterion_remote.phone_live import _authorized
record = load()
token = record.get("token", "") if isinstance(record, dict) else ""
print("REGISTERED_ANDROID_DEVICE=" + str(bool(record)).lower())
print("NATIVE_ANDROID_KEY_PRESENT=" + str(len(token) >= 32).lower())
print("DIRECT_MCP_NATIVE_AUTH_MATCH=" + str(_authorized(token) if token else False).lower())
