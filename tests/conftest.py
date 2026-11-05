"""Stable isolated auth and allowed-root settings before API module imports."""
import os
from pathlib import Path
os.environ.setdefault('ASTERION_API_TOKEN','test-asterion-token-abcdefghijklmnopqrstuvwxyz')
os.environ.setdefault('ASTERION_REMOTE_ROOT',str(Path(__file__).resolve().parents[1]))
