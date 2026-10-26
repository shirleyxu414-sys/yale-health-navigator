"""Settings and .env loading. The API key is only ever read from the environment."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"

MODEL = "gpt-6-luna"  # course rule: the only model this app may use, for every agent
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"
MODEL_TIMEOUT = 60.0

# Budget guard: input tokens per browser session, and a larger cap per network address so a new session id is no way around it.
SESSION_TOKEN_CAP = 200_000
ADDRESS_TOKEN_CAP = 1_000_000


def load_env(root: Path = ROOT) -> None:
    """Load .env from the repo folder first, then from the folder above it.

    load_dotenv does not override values that are already set, so the repo's own .env wins
    over the one a level up, and a key already in the shell wins over both.
    """
    for folder in (root, root.parent):
        env_file = folder / ".env"
        if env_file.is_file():
            load_dotenv(env_file, override=False)


def make_client() -> OpenAI:
    key = os.environ.get("PORTKEY_API_KEY")
    if not key:
        raise RuntimeError(
            "PORTKEY_API_KEY is not set. Put it in a .env file in the repo folder or in the folder above it."
        )
    return OpenAI(api_key=key, base_url=PORTKEY_BASE_URL, timeout=MODEL_TIMEOUT, max_retries=2)


load_env()

# Chat and audit logs (both are gitignored). The chat log keeps the question text because the project asked for it;
# set this to False to keep only the question's length instead.
CHAT_LOG_QUESTIONS = True
CHAT_LOG = "chat_log.json"
AUDIT_LOG = "audit_trail.json"
CHAT_LOG_LIMIT = 5000
