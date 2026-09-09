"""Thin Langfuse wrapper — no-ops when LANGFUSE_PUBLIC_KEY is unset.

    from trace import span, flush
    with span("extract_turn", input=convo) as s:
        ...
        s.update(output=fields, usage_details={"input": in_tok, "output": out_tok})

Only `input` is read at span open; everything else (output, model, metadata,
usage_details, cost_details, level, status_message) must go through `s.update()`.
Pass `as_type="span"` for a non-LLM observation (STT leg, call-level wrapper).
"""

from __future__ import annotations

import contextlib
import os

# Load the repo .env before checking for keys — callers that import trace
# (transitively, via extract) before their own load_dotenv would otherwise get a
# silent no-op. load_dotenv does not override already-set vars, so this is safe.
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except Exception:  # noqa: BLE001
    pass

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
def span(name: str, *, as_type: str = "generation", **start_kw):
    """A Langfuse observation. `generation` (default) carries token/cost; use
    `span` for a non-LLM step (STT leg, call-level wrapper). Nesting is implicit —
    a span opened inside another's `with` block becomes its child."""
    if not _ENABLED or _client is None:
        yield _Span(None)
        return
    inp = start_kw.get("input")
    obs = getattr(_client, "start_as_current_observation", None)
    try:
        if obs is not None:  # langfuse v4
            cm = obs(name=name, input=inp, as_type=as_type)
        else:                # langfuse v3
            gen = getattr(_client, "start_as_current_generation", _client.start_as_current_span)
            cm = gen(name=name, input=inp)
        with cm as s:
            yield _Span(s)
    except Exception:  # noqa: BLE001
        yield _Span(None)


def flush() -> None:
    if _client is not None:
        with contextlib.suppress(Exception):
            _client.flush()
