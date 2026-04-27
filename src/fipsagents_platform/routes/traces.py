"""REST API for cross-agent traces (scaffolded -- proof point pending).

Returns 501 until the trace-store proof point lands. See open issues
in this repo.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter()


def _not_implemented() -> None:
    raise HTTPException(
        status_code=501,
        detail=(
            "traces endpoint not yet implemented; track progress at "
            "https://github.com/fips-agents/fipsagents-platform/issues"
        ),
    )


@router.get("")
async def list_traces() -> list:
    _not_implemented()


@router.get("/{trace_id}")
async def get_trace(trace_id: str) -> dict:
    _not_implemented()
