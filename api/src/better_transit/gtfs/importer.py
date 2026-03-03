import asyncio
import logging
import tempfile
import time
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from better_transit.config import settings
from better_transit.gtfs.downloader import download_and_extract
from better_transit.gtfs.loader import load_gtfs_data
from better_transit.gtfs.parser import parse_gtfs_directory

logger = logging.getLogger(__name__)


async def run_import(
    engine: AsyncEngine, gtfs_url: str | None = None
) -> dict[str, int]:
    """Run the full GTFS import pipeline.

    1. Download and extract GTFS ZIP
    2. Parse CSV files into validated models
    3. Load into database (truncate + insert)

    Returns row counts per table.
    """
    url = gtfs_url or settings.gtfs_static_url
    start = time.monotonic()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / "gtfs"
        logger.info("Starting GTFS import from %s", url)

        # Download and extract
        gtfs_dir = download_and_extract(url, tmp_path)

        # Parse
        logger.info("Parsing GTFS files...")
        data = parse_gtfs_directory(gtfs_dir)

        # Load
        logger.info("Loading into database...")
        stats = await load_gtfs_data(engine, data)

    elapsed = time.monotonic() - start
    logger.info("GTFS import complete in %.1fs", elapsed)
    for table, count in stats.items():
        logger.info("  %s: %d rows", table, count)

    return stats


async def _main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    engine = create_async_engine(settings.database_url)
    try:
        await run_import(engine)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main())
