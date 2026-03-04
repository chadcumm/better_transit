import io
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from better_transit.gtfs.downloader import DOWNLOAD_TIMEOUT, download_and_extract


@pytest.fixture
def fake_gtfs_zip_bytes() -> bytes:
    """Create a minimal fake GTFS zip in memory."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("agency.txt", "agency_id,agency_name\nKCATA,Test Agency\n")
        zf.writestr("stops.txt", "stop_id,stop_name\n1,Test Stop\n")
    return buf.getvalue()


@pytest.fixture
def mock_urlopen(fake_gtfs_zip_bytes: bytes):
    """Patch urlopen to return fake zip bytes."""
    mock_response = MagicMock()
    mock_response.read.side_effect = [fake_gtfs_zip_bytes, b""]
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)
    target = "better_transit.gtfs.downloader.urllib.request.urlopen"
    with patch(target, return_value=mock_response) as mock:
        yield mock


def test_download_and_extract(mock_urlopen, tmp_path: Path):
    result_dir = download_and_extract("https://example.com/gtfs.zip", tmp_path / "output")

    assert result_dir.is_dir()
    assert (result_dir / "agency.txt").exists()
    assert (result_dir / "stops.txt").exists()


def test_download_and_extract_returns_path_with_txt_files(mock_urlopen, tmp_path: Path):
    result_dir = download_and_extract("http://example.com/gtfs.zip", tmp_path / "output")

    txt_files = list(result_dir.glob("*.txt"))
    assert len(txt_files) == 2


def test_download_uses_timeout(mock_urlopen, tmp_path: Path):
    download_and_extract("https://example.com/gtfs.zip", tmp_path / "output")
    mock_urlopen.assert_called_once_with("https://example.com/gtfs.zip", timeout=DOWNLOAD_TIMEOUT)


def test_rejects_file_scheme():
    with pytest.raises(ValueError, match="not allowed"):
        download_and_extract("file:///etc/passwd", Path("/tmp/out"))


def test_rejects_ftp_scheme():
    with pytest.raises(ValueError, match="not allowed"):
        download_and_extract("ftp://example.com/gtfs.zip", Path("/tmp/out"))


def test_download_aborts_if_too_large(tmp_path: Path):
    """Download should abort if response exceeds MAX_DOWNLOAD_SIZE."""
    small_limit = 50_000  # 50 KB

    # Build data larger than the limit
    big_data = b"x" * (small_limit + 10_000)

    mock_response = MagicMock()
    # Return all data in one chunk, then EOF
    mock_response.read.side_effect = [big_data, b""]
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("better_transit.gtfs.downloader.urllib.request.urlopen", return_value=mock_response), \
         patch("better_transit.gtfs.downloader.MAX_DOWNLOAD_SIZE", small_limit):
        with pytest.raises(ValueError, match="size limit"):
            download_and_extract("https://example.com/gtfs.zip", tmp_path / "output")


def test_rejects_zip_bomb(tmp_path: Path):
    """Reject zip files with excessive uncompressed size."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Write a large file that compresses well
        zf.writestr("big.txt", "A" * 1_000_000)
    zip_bytes = buf.getvalue()

    mock_response = MagicMock()
    mock_response.read.side_effect = [zip_bytes, b""]
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("better_transit.gtfs.downloader.urllib.request.urlopen", return_value=mock_response), \
         patch("better_transit.gtfs.downloader.MAX_UNCOMPRESSED_SIZE", 500_000):
        with pytest.raises(ValueError, match="uncompressed size"):
            download_and_extract("https://example.com/gtfs.zip", tmp_path / "output")
