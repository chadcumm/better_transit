from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from better_transit.gtfs.importer import run_import


@pytest.fixture
def fake_gtfs_dir(tmp_path: Path) -> Path:
    """Create a minimal GTFS directory with fixture files."""
    gtfs_dir = tmp_path / "gtfs"
    gtfs_dir.mkdir()

    (gtfs_dir / "agency.txt").write_text(
        "agency_id,agency_name,agency_url,agency_timezone,agency_lang,agency_phone,agency_fare_url\n"
        "KCATA,Kansas City Area Transportation Authority,http://www.kcata.org,America/Chicago,en,816-221-0660,\n"
    )
    (gtfs_dir / "routes.txt").write_text(
        "route_id,agency_id,route_short_name,route_long_name,route_desc,route_type,route_url,route_color,route_text_color\n"
        "101,KCATA,101,State,101,3,,C0C0C0,000000\n"
    )
    (gtfs_dir / "stops.txt").write_text(
        "stop_id,stop_code,stop_name,stop_desc,stop_lat,stop_lon,zone_id,stop_url,location_type,parent_station,stop_timezone,wheelchair_boarding\n"
        "1,1,Test Stop,,39.1,-94.5,,,,,,0\n"
    )
    (gtfs_dir / "trips.txt").write_text(
        "route_id,service_id,trip_id,trip_headsign,trip_short_name,direction_id,block_id,shape_id,wheelchair_accessible,bikes_allowed\n"
        "101,25.0.1,T1,Test,,0,1,S1,0,0\n"
    )
    (gtfs_dir / "stop_times.txt").write_text(
        "trip_id,arrival_time,departure_time,stop_id,stop_sequence,stop_headsign,pickup_type,drop_off_type,shape_dist_traveled,timepoint\n"
        "T1, 8:00:00, 8:00:00,1,1,,0,0,,1\n"
    )
    (gtfs_dir / "calendar.txt").write_text(
        "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n"
        "25.0.1,1,1,1,1,1,0,0,20260215,20260404\n"
    )
    (gtfs_dir / "calendar_dates.txt").write_text(
        "service_id,date,exception_type\n"
        "25.39.1,20260217,1\n"
    )
    (gtfs_dir / "shapes.txt").write_text(
        "shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence,shape_dist_traveled\n"
        "S1,39.099234,-94.573962,1,0.0\n"
        "S1,39.099617,-94.573939,2,0.043\n"
    )
    return gtfs_dir


@pytest.mark.asyncio
async def test_run_import_orchestrates_pipeline(fake_gtfs_dir: Path):
    mock_engine = AsyncMock()

    with (
        patch("better_transit.gtfs.importer.download_and_extract", return_value=fake_gtfs_dir),
        patch("better_transit.gtfs.importer.load_gtfs_data", new_callable=AsyncMock) as mock_load,
    ):
        mock_load.return_value = {
            "agency": 1,
            "routes": 1,
            "stops": 1,
            "trips": 1,
            "stop_times": 1,
            "calendar": 1,
            "calendar_dates": 1,
            "shapes": 2,
            "shape_geoms": 1,
        }
        stats = await run_import(mock_engine, "http://example.com/gtfs.zip")

    assert stats["agency"] == 1
    assert stats["stops"] == 1
    mock_load.assert_called_once()
