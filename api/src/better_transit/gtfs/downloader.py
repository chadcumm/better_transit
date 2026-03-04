import logging
import urllib.request
import zipfile
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

ALLOWED_SCHEMES = {"http", "https"}
DOWNLOAD_TIMEOUT = 60
MAX_DOWNLOAD_SIZE = 100 * 1024 * 1024  # 100 MB
MAX_UNCOMPRESSED_SIZE = 500 * 1024 * 1024  # 500 MB
MAX_COMPRESSION_RATIO = 100
CHUNK_SIZE = 8192


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
    Aborts if download exceeds MAX_DOWNLOAD_SIZE.
    Rejects zip bombs (excessive uncompressed size or compression ratio).
    """
    _validate_url(url)
    extract_to.mkdir(parents=True, exist_ok=True)
    zip_path = extract_to / "gtfs.zip"

    logger.info("Downloading GTFS feed from %s", url)
    with urllib.request.urlopen(url, timeout=DOWNLOAD_TIMEOUT) as response:
        bytes_downloaded = 0
        with open(zip_path, "wb") as out_file:
            while True:
                chunk = response.read(CHUNK_SIZE)
                if not chunk:
                    break
                bytes_downloaded += len(chunk)
                if bytes_downloaded > MAX_DOWNLOAD_SIZE:
                    out_file.close()
                    zip_path.unlink(missing_ok=True)
                    raise ValueError(
                        f"Download exceeds {MAX_DOWNLOAD_SIZE} byte size limit"
                    )
                out_file.write(chunk)

    logger.info("Downloaded %d bytes", bytes_downloaded)

    logger.info("Extracting to %s", extract_to)
    with zipfile.ZipFile(zip_path, "r") as zf:
        # Path traversal check
        for member in zf.namelist():
            member_path = (extract_to / member).resolve()
            if not str(member_path).startswith(str(extract_to.resolve())):
                raise ValueError(f"Zip member {member!r} would extract outside target directory")

        # Zip bomb check: excessive uncompressed size or compression ratio
        total_uncompressed = sum(info.file_size for info in zf.infolist())
        total_compressed = sum(info.compress_size for info in zf.infolist())
        if total_uncompressed > MAX_UNCOMPRESSED_SIZE:
            zip_path.unlink(missing_ok=True)
            raise ValueError(
                f"Zip uncompressed size ({total_uncompressed} bytes) exceeds "
                f"{MAX_UNCOMPRESSED_SIZE} byte limit"
            )
        if total_compressed > 0:
            ratio = total_uncompressed / total_compressed
            if ratio > MAX_COMPRESSION_RATIO:
                zip_path.unlink(missing_ok=True)
                raise ValueError(
                    f"Zip compression ratio ({ratio:.0f}:1) exceeds "
                    f"{MAX_COMPRESSION_RATIO}:1 limit"
                )

        zf.extractall(extract_to)

    zip_path.unlink(missing_ok=True)
    logger.info("Extracted %d files", len(list(extract_to.glob("*.txt"))))
    return extract_to
