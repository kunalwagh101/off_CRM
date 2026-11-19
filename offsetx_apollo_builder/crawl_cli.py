"""Seed, inspect and run the persistent anonymous public-web crawler."""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
import time
from pathlib import Path

from .crawl import Frontier, FrontierError, FrontierRunner
from .discovery import CrawlPolicy


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Persistent public crawl frontier; no logged-in platform sessions.')
    parser.add_argument('--db', type=Path, default=Path('local_data/crawl.db'))
    parser.add_argument('--workspace', default='local')
    parser.add_argument('--allow', action='append', required=True, help='Permitted public domain; repeat to add domains.')
    parser.add_argument('--delay', type=float, default=0.75, help='Minimum request spacing in seconds; robots may require longer.')
    parser.add_argument('--max-depth', type=int, default=1)
    parser.add_argument('--revisit-seconds', type=float, default=86400)
    parser.add_argument('--max-revisit-seconds', type=float, default=2592000)
    actions = parser.add_subparsers(dest='action', required=True)
    seed = actions.add_parser('seed', help='Add public URLs without fetching them.')
    seed.add_argument('urls', nargs='+')
    remove = actions.add_parser('remove', help='Remove an unclaimed URL from this workspace queue.')
    remove.add_argument('url')
    inspect = actions.add_parser('inspect', help='Show queue metadata and next due time.')
    inspect.add_argument('--limit', type=int, default=1000)
    for name in ('run', 'watch'):
        command = actions.add_parser(name, help='Process one due batch.' if name == 'run' else 'Repeat bounded batches until interrupted.')
        command.add_argument('--max-pages', type=int, default=20)
        if name == 'watch':
            command.add_argument('--poll-seconds', type=float, default=5)
    args = parser.parse_args(argv)
    frontier = runner = None
    try:
        policy = CrawlPolicy(allowed_domains=tuple(args.allow), request_delay_seconds=args.delay,
                             max_depth=args.max_depth)
        frontier = Frontier(args.db, policy, workspace_id=args.workspace,
            revisit_seconds=args.revisit_seconds, max_revisit_seconds=args.max_revisit_seconds)
        if args.action == 'seed':
            print(json.dumps({'added': frontier.seed(args.urls), 'frontier': frontier.inspect()}))
        elif args.action == 'remove':
            print(json.dumps({'removed': frontier.remove(args.url)}))
        elif args.action == 'inspect':
            print(json.dumps(frontier.inspect(limit=args.limit)))
        else:
            if args.action == 'watch' and (not math.isfinite(args.poll_seconds) or not 0.1 <= args.poll_seconds <= 60):
                raise FrontierError('Watch polling must be between 0.1 and 60 seconds.')
            runner = FrontierRunner(frontier)
            while True:
                batch = runner.run_due(max_pages=args.max_pages)
                print(json.dumps(batch.to_dict()), flush=True)
                if args.action == 'run':
                    return 1 if batch.failed else 0
                time.sleep(args.poll_seconds)
        return 0
    except KeyboardInterrupt:
        return 130
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(json.dumps({'error': str(exc), 'action': 'Check the allow-list, URL, scheduler settings and database permissions.'}), file=sys.stderr)
        return 2
    finally:
        if runner is not None:
            runner.close()
        if frontier is not None:
            frontier.close()


if __name__ == '__main__':
    raise SystemExit(main())
