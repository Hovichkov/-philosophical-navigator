"""Latency instrumentation (M3.3.1): what one Claude Code CLI call cost in time and tokens."""

from __future__ import annotations


def cli_usage(payload: dict, wall_seconds: float) -> dict:
    """Usage record for one `claude -p` call, from its JSON payload and measured wall time."""
    u = payload.get("usage") or {}
    details = u.get("output_tokens_details") or {}
    return {
        "wall_seconds": round(wall_seconds, 2),
        "cli_duration_ms": payload.get("duration_ms"),
        "api_duration_ms": payload.get("duration_api_ms"),
        "num_turns": payload.get("num_turns"),
        "input_tokens": u.get("input_tokens"),
        "cache_read_tokens": u.get("cache_read_input_tokens"),
        "cache_creation_tokens": u.get("cache_creation_input_tokens"),
        "output_tokens": u.get("output_tokens"),
        "thinking_tokens": details.get("thinking_tokens"),
        "total_cost_usd_list": payload.get("total_cost_usd"),
        "models": list(payload.get("modelUsage", {})),
    }


def cli_error_message(payload: dict) -> str:
    """The CLI's own explanation first (e.g. a usage limit or login problem), then the raw payload."""
    head = {k: payload.get(k) for k in ("subtype", "is_error", "result", "api_error_status") if payload.get(k) is not None}
    return f"CLI error: {head} | raw: {str(payload)[:400]}"
