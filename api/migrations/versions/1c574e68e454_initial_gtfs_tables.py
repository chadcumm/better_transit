"""initial gtfs tables

Revision ID: 1c574e68e454
Revises:
Create Date: 2026-03-02 18:34:31.258895

"""
from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1c574e68e454"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "agency",
        sa.Column("agency_id", sa.String(), nullable=False),
        sa.Column("agency_name", sa.String(), nullable=False),
        sa.Column("agency_url", sa.String(), nullable=False),
        sa.Column("agency_timezone", sa.String(), nullable=False),
        sa.Column("agency_lang", sa.String(), nullable=True),
        sa.Column("agency_phone", sa.String(), nullable=True),
        sa.Column("agency_fare_url", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("agency_id"),
    )
    op.create_table(
        "routes",
        sa.Column("route_id", sa.String(), nullable=False),
        sa.Column("agency_id", sa.String(), nullable=False),
        sa.Column("route_short_name", sa.String(), nullable=True),
        sa.Column("route_long_name", sa.String(), nullable=True),
        sa.Column("route_desc", sa.String(), nullable=True),
        sa.Column("route_type", sa.Integer(), nullable=False),
        sa.Column("route_url", sa.String(), nullable=True),
        sa.Column("route_color", sa.String(), nullable=True),
        sa.Column("route_text_color", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("route_id"),
    )
    op.create_table(
        "stops",
        sa.Column("stop_id", sa.String(), nullable=False),
        sa.Column("stop_code", sa.String(), nullable=True),
        sa.Column("stop_name", sa.String(), nullable=False),
        sa.Column("stop_desc", sa.String(), nullable=True),
        sa.Column("stop_lat", sa.Float(), nullable=False),
        sa.Column("stop_lon", sa.Float(), nullable=False),
        sa.Column("zone_id", sa.String(), nullable=True),
        sa.Column("stop_url", sa.String(), nullable=True),
        sa.Column("location_type", sa.Integer(), nullable=True),
        sa.Column("parent_station", sa.String(), nullable=True),
        sa.Column("stop_timezone", sa.String(), nullable=True),
        sa.Column("wheelchair_boarding", sa.Integer(), nullable=True),
        sa.Column(
            "geom",
            geoalchemy2.types.Geometry(
                geometry_type="POINT", srid=4326, from_text="ST_GeomFromEWKT",
                name="geometry",
            ),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("stop_id"),
    )
    op.create_index("ix_stops_geom", "stops", ["geom"], postgresql_using="gist")
    op.create_table(
        "trips",
        sa.Column("trip_id", sa.String(), nullable=False),
        sa.Column("route_id", sa.String(), nullable=False),
        sa.Column("service_id", sa.String(), nullable=False),
        sa.Column("trip_headsign", sa.String(), nullable=True),
        sa.Column("trip_short_name", sa.String(), nullable=True),
        sa.Column("direction_id", sa.Integer(), nullable=True),
        sa.Column("block_id", sa.String(), nullable=True),
        sa.Column("shape_id", sa.String(), nullable=True),
        sa.Column("wheelchair_accessible", sa.Integer(), nullable=True),
        sa.Column("bikes_allowed", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("trip_id"),
    )
    op.create_index(
        "ix_trips_route_service", "trips", ["route_id", "service_id"]
    )
    op.create_table(
        "stop_times",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("trip_id", sa.String(), nullable=False),
        sa.Column("arrival_time", sa.String(), nullable=False),
        sa.Column("departure_time", sa.String(), nullable=False),
        sa.Column("stop_id", sa.String(), nullable=False),
        sa.Column("stop_sequence", sa.Integer(), nullable=False),
        sa.Column("stop_headsign", sa.String(), nullable=True),
        sa.Column("pickup_type", sa.Integer(), nullable=True),
        sa.Column("drop_off_type", sa.Integer(), nullable=True),
        sa.Column("shape_dist_traveled", sa.Float(), nullable=True),
        sa.Column("timepoint", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_stop_times_stop_departure",
        "stop_times",
        ["stop_id", "departure_time"],
    )
    op.create_index(
        "ix_stop_times_trip_seq", "stop_times", ["trip_id", "stop_sequence"]
    )
    op.create_table(
        "calendar",
        sa.Column("service_id", sa.String(), nullable=False),
        sa.Column("monday", sa.Boolean(), nullable=False),
        sa.Column("tuesday", sa.Boolean(), nullable=False),
        sa.Column("wednesday", sa.Boolean(), nullable=False),
        sa.Column("thursday", sa.Boolean(), nullable=False),
        sa.Column("friday", sa.Boolean(), nullable=False),
        sa.Column("saturday", sa.Boolean(), nullable=False),
        sa.Column("sunday", sa.Boolean(), nullable=False),
        sa.Column("start_date", sa.String(), nullable=False),
        sa.Column("end_date", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("service_id"),
    )
    op.create_table(
        "calendar_dates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("service_id", sa.String(), nullable=False),
        sa.Column("date", sa.String(), nullable=False),
        sa.Column("exception_type", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_calendar_dates_service_date",
        "calendar_dates",
        ["service_id", "date"],
    )
    op.create_table(
        "shapes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("shape_id", sa.String(), nullable=False),
        sa.Column("shape_pt_lat", sa.Float(), nullable=False),
        sa.Column("shape_pt_lon", sa.Float(), nullable=False),
        sa.Column("shape_pt_sequence", sa.Integer(), nullable=False),
        sa.Column("shape_dist_traveled", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "shape_geoms",
        sa.Column("shape_id", sa.String(), nullable=False),
        sa.Column(
            "geom",
            geoalchemy2.types.Geometry(
                geometry_type="LINESTRING",
                srid=4326,
                from_text="ST_GeomFromEWKT",
                name="geometry",
            ),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("shape_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("shape_geoms")
    op.drop_table("shapes")
    op.drop_index("ix_calendar_dates_service_date", table_name="calendar_dates")
    op.drop_table("calendar_dates")
    op.drop_table("calendar")
    op.drop_index("ix_stop_times_trip_seq", table_name="stop_times")
    op.drop_index("ix_stop_times_stop_departure", table_name="stop_times")
    op.drop_table("stop_times")
    op.drop_index("ix_trips_route_service", table_name="trips")
    op.drop_table("trips")
    op.drop_index("ix_stops_geom", table_name="stops")
    op.drop_table("stops")
    op.drop_table("routes")
    op.drop_table("agency")
