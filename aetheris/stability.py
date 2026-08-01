"""Small, dependency-free health helpers used by the core loader and .health."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def module_health_snapshot(
    modules: Iterable[Any],
    failures: dict[int, str],
    failed_module_count: int = 0,
) -> dict[str, int]:
    """Return stable module counters without exposing exception details."""
    loaded = failed = core_failed = 0
    for module in modules:
        if module is None:
            continue
        if id(module) in failures:
            failed += 1
            if str(getattr(module, "__origin__", "")).startswith("<core"):
                core_failed += 1
        else:
            loaded += 1
    return {"loaded": loaded, "failed": failed + failed_module_count, "core_failed": core_failed}


def safe_status(value: Any, ok: bool | None = None) -> str:
    """Format a compact status value for a Telegram health report."""
    if ok is True:
        return "OK"
    if ok is False:
        return "FAIL"
    return str(value)
