import logging
import urllib.request
import zipfile
from pathlib import Path

logger = logging.getLogger(__name__)


def download_and_extract(url: str, extract_to: Path) -> Path:
    """Download a GTFS ZIP from url and extract to extract_to directory.

    Returns the path to the directory containing extracted .txt files.
    """
    extract_to.mkdir(parents=True, exist_ok=True)
    zip_path = extract_to / "gtfs.zip"

    logger.info("Downloading GTFS feed from %s", url)
    downloaded_path, _ = urllib.request.urlretrieve(url, zip_path)

    logger.info("Extracting to %s", extract_to)
    with zipfile.ZipFile(downloaded_path, "r") as zf:
        zf.extractall(extract_to)

    Path(downloaded_path).unlink(missing_ok=True)
    logger.info("Extracted %d files", len(list(extract_to.glob("*.txt"))))
    return extract_to
