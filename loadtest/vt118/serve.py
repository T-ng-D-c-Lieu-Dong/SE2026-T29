"""Launch the Booking API for the VT-118 load experiment with a chosen notifier behaviour.

The launcher exists only for the load harness. Production wiring is unchanged: the API keeps the
default ``LoggingBookingNotifier``. A replacement notifier is attached to ``app.state`` of this
process only, so no fault switch is added to the production settings (see plan review R4).

Usage (from the repository root)::

    BOOKING_DATABASE_URL=postgresql+asyncpg://booking:booking@127.0.0.1:55432/booking_load_test \
    PYTHONPATH=backend python loadtest/vt118/serve.py --notifier hang --port 8018

``--notifier`` values:
    default  production default notifier (structured log line)
    ok       returns immediately
    fail     raises ``ConnectionError`` on every event
    hang     never completes; only the notification timeout ends it
"""

from __future__ import annotations

import argparse
import asyncio
import logging

import uvicorn


class LoadTestNotifier:
    def __init__(self, mode: str) -> None:
        self.mode = mode

    async def send(self, event: object) -> None:
        if self.mode == "fail":
            raise ConnectionError("load-test: notification channel is down")
        if self.mode == "hang":
            await asyncio.Event().wait()


def build_app(mode: str):
    import app.main
    from app.main import create_app

    logging.getLogger(__name__).warning("serving backend code from %s", app.main.__file__)
    application = create_app()
    if mode == "default":
        return application
    try:
        import app.services.notifications  # noqa: F401
    except ImportError:
        logging.getLogger(__name__).warning(
            "app.services.notifications not found: running baseline without notifier"
        )
        return application
    application.state.booking_notifier = LoadTestNotifier(mode)
    return application


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--notifier", choices=("default", "ok", "fail", "hang"), default="default")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8018)
    args = parser.parse_args()
    uvicorn.run(
        build_app(args.notifier),
        host=args.host,
        port=args.port,
        log_level="warning",
        access_log=False,
    )


if __name__ == "__main__":
    main()
