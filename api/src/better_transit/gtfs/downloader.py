import logging
import urllib.request
import zipfile
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

ALLOWED_SCHEMES = {"http", "https"}


def _validate_url(url: str) -> None:
    """Validate that the URL uses an allowed scheme."""
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise ValueError(
            f"URL scheme '{parsed.scheme}' is not allowed. Use http:// or https://"
        )


def download_and_extract(url: str, extract_to: Path) -> Path:
    """Download a GTFS ZIP from url and extract to extract_to directory.

    Returns the path to the directory containing extracted .txt files.
    """
    _validate_url(url)
    extract_to.mkdir(parents=True, exist_ok=True)
    zip_path = extract_to / "gtfs.zip"

    logger.info("Downloading GTFS feed from %s", url)
    downloaded_path, _ = urllib.request.urlretrieve(url, zip_path)

    logger.info("Extracting to %s", extract_to)
    with zipfile.ZipFile(downloaded_path, "r") as zf:
        for member in zf.namelist():
            member_path = (extract_to / member).resolve()
            if not str(member_path).startswith(str(extract_to.resolve())):
                raise ValueError(f"Zip member {member!r} would extract outside target directory")
        zf.extractall(extract_to)

    Path(downloaded_path).unlink(missing_ok=True)
    logger.info("Extracted %d files", len(list(extract_to.glob("*.txt"))))
    return extract_to
