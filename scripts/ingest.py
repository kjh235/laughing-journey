"""
FFL data ingestion CLI.

Usage:
    python scripts/ingest.py [--local-file PATH] [--dry-run]
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Ingest ATF FFL data into the database")
    p.add_argument(
        "--local-file",
        type=Path,
        default=None,
        help="Use a local ATF .txt file instead of downloading",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and report counts without writing to the database",
    )
    return p.parse_args()


async def _run(args: argparse.Namespace) -> None:
    if args.dry_run:
        from ffl.ingestion.parser import parse_atf_file
        from ffl.ingestion.downloader import download_atf_data

        path = args.local_file or await download_atf_data()
        df = parse_atf_file(path)
        print(f"Dry run: would ingest {len(df)} records")
        print(df.head(5).to_string())
        return

    from ffl.ingestion.pipeline import run_pipeline

    stats = await run_pipeline(local_file=args.local_file)
    print("Ingestion complete:")
    for k, v in stats.items():
        print(f"  {k}: {v}")


def main() -> None:
    args = parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
