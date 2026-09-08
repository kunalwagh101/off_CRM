from __future__ import annotations

import argparse

import uvicorn
from dotenv import load_dotenv

from .api.app import create_app
from .api.config import AppSettings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the off_CRM local web CRM")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args(argv)
    load_dotenv()
    settings = AppSettings.from_env()
    if args.host:
        settings.host = args.host
    if args.port:
        settings.port = args.port
    settings.validate()
    if settings.api_token and not settings.demo_login_enabled:
        # Printed, not logged: a token nobody can see is a lock with no key, and
        # the first thing an owner needs after this change is the value to paste
        # into the UI. Never printed when a demo login exists — then the browser
        # already has a way in and this would be gratuitous exposure.
        print(f"\n  off_CRM API token: {settings.api_token}")
        print(f"  stored at:         {settings.data_dir / settings.TOKEN_FILENAME}")
        print("  Paste it into the web UI once; it is kept in that browser.\n")
    uvicorn.run(
        create_app(settings),
        host=settings.host,
        port=settings.port,
        log_level="info",
        access_log=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
