"""
Temporary JSON decode tripwire for locating malformed escape sequences.
Patch json.loads/json.load to log context and stack when a JSONDecodeError occurs.
Remove after debugging.
"""

import json
import sys
import traceback
from typing import Any

_original_loads = json.loads
_original_load = json.load
_patched = False


def _context_slice(text: str, pos: int, window: int = 60) -> str:
    start = max(0, pos - window)
    end = min(len(text), pos + window)
    return text[start:end]


def _log_decode_error(exc: json.JSONDecodeError, raw: str, source_hint: str) -> None:
    snippet = _context_slice(raw, exc.pos)
    print(
        f"\n[json-tripwire] JSON decode failed: pos={exc.pos} line={exc.lineno} col={exc.colno}",
        file=sys.stderr,
    )
    print(f"[json-tripwire] source={source_hint}", file=sys.stderr)
    print(f"[json-tripwire] context={repr(snippet)}", file=sys.stderr)
    print("[json-tripwire] stack:\n" + "".join(traceback.format_stack(limit=20)), file=sys.stderr)


def loads(s: Any, *args: Any, **kwargs: Any):  # type: ignore[override]
    try:
        return _original_loads(s, *args, **kwargs)
    except json.JSONDecodeError as exc:  # pragma: no cover - diagnostics only
        head = repr(str(s)[:80])
        _log_decode_error(exc, str(s), f"inline type={type(s)} len={len(str(s))} head={head}")
        raise


def load(fp: Any, *args: Any, **kwargs: Any):  # type: ignore[override]
    try:
        text = fp.read()
    except Exception:
        return _original_load(fp, *args, **kwargs)

    try:
        return _original_loads(text, *args, **kwargs)
    except json.JSONDecodeError as exc:  # pragma: no cover - diagnostics only
        name = getattr(fp, "name", None)
        _log_decode_error(exc, text, f"file={name} len={len(text)}")
        raise


def install() -> None:
    global _patched
    if _patched:
        return
    json.loads = loads  # type: ignore[assignment]
    json.load = load  # type: ignore[assignment]
    _patched = True


install()
