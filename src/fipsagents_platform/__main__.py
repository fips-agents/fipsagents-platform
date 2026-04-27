"""Entrypoint for ``python -m fipsagents_platform``.

Wraps uvicorn so the package is runnable without an explicit uvicorn invocation.
"""

from __future__ import annotations

import os


def main() -> None:
    import uvicorn

    uvicorn.run(
        "fipsagents_platform.app:app",
        host=os.environ.get("PLATFORM_HOST", "0.0.0.0"),
        port=int(os.environ.get("PLATFORM_PORT", "8080")),
        log_level=os.environ.get("PLATFORM_LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    main()
