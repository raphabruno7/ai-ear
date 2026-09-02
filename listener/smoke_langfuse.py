"""One trace to Langfuse, to confirm keys work and give you a URL to screenshot.

    1. Create a free project at https://cloud.langfuse.com
    2. Settings -> API Keys -> put the pair in ../.env:
         LANGFUSE_PUBLIC_KEY=pk-lf-...
         LANGFUSE_SECRET_KEY=sk-lf-...
         LANGFUSE_HOST=https://cloud.langfuse.com   (or the EU/self-host URL)
    3. .venv/bin/python smoke_langfuse.py
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

if not os.environ.get("LANGFUSE_PUBLIC_KEY"):
    sys.exit("LANGFUSE_PUBLIC_KEY not set — see this file's docstring.")

from trace import _client, span, flush  # noqa: E402

with span("smoke", input={"hello": "call-copilot"}) as s:
    s.update(output={"ok": True}, metadata={"source": "smoke_langfuse.py"})

flush()

url = None
if _client is not None:
    try:
        url = _client.get_trace_url()
    except Exception:  # noqa: BLE001
        pass
print("sent one trace to Langfuse.", f"View: {url}" if url else "Check the dashboard.")
