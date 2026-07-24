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
