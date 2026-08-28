"""Thin Langfuse wrapper — no-ops when LANGFUSE_PUBLIC_KEY is unset.

    from trace import span, flush
    with span("extract_turn", input=convo) as s:
        ...
        s.update(output=fields, usage={"input": in_tok, "output": out_tok})
"""

from __future__ import annotations

import contextlib
import os

_ENABLED = bool(os.environ.get("LANGFUSE_PUBLIC_KEY"))
_client = None

if _ENABLED:
    try:
        from langfuse import Langfuse
        _client = Langfuse()  # reads LANGFUSE_PUBLIC_KEY / SECRET_KEY / HOST
    except Exception:  # noqa: BLE001
        _ENABLED = False


class _Span:
    def __init__(self, inner):
        self._inner = inner

    def update(self, **kw):
        if self._inner is not None:
            with contextlib.suppress(Exception):
                self._inner.update(**kw)


@contextlib.contextmanager
def span(name: str, **start_kw):
    if not _ENABLED or _client is None:
        yield _Span(None)
        return
    try:
        with _client.start_as_current_span(name=name, input=start_kw.get("input")) as s:
            yield _Span(s)
    except Exception:  # noqa: BLE001
        yield _Span(None)


def flush() -> None:
    if _client is not None:
        with contextlib.suppress(Exception):
            _client.flush()
