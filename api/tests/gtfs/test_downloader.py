import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from better_transit.gtfs.downloader import download_and_extract


@pytest.fixture
def fake_gtfs_zip(tmp_path: Path) -> Path:
    """Create a minimal fake GTFS zip for testing."""
    zip_path = tmp_path / "fake_gtfs.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("agency.txt", "agency_id,agency_name\nKCATA,Test Agency\n")
        zf.writestr("stops.txt", "stop_id,stop_name\n1,Test Stop\n")
    return zip_path


def test_download_and_extract(fake_gtfs_zip: Path, tmp_path: Path):
    fake_url = f"file://{fake_gtfs_zip}"

    with patch("better_transit.gtfs.downloader.urllib.request.urlretrieve") as mock_retrieve:
        mock_retrieve.return_value = (str(fake_gtfs_zip), None)
        result_dir = download_and_extract(fake_url, tmp_path / "output")

    assert result_dir.is_dir()
    assert (result_dir / "agency.txt").exists()
    assert (result_dir / "stops.txt").exists()


def test_download_and_extract_returns_path_with_txt_files(fake_gtfs_zip: Path, tmp_path: Path):
    with patch("better_transit.gtfs.downloader.urllib.request.urlretrieve") as mock_retrieve:
        mock_retrieve.return_value = (str(fake_gtfs_zip), None)
        result_dir = download_and_extract("http://example.com/gtfs.zip", tmp_path / "output")

    txt_files = list(result_dir.glob("*.txt"))
    assert len(txt_files) == 2
