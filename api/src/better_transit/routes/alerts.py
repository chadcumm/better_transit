from fastapi import APIRouter

from better_transit.models.alerts import AlertResponse
from better_transit.realtime.client import fetch_service_alerts

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertResponse])
async def list_alerts():
    """List active service alerts from GTFS-RT feed."""
    alerts = fetch_service_alerts()
    return [
        AlertResponse(
            alert_id=a["alert_id"],
            header=a["header"],
            description=a["description"],
            severity=a["severity"],
            affected_route_ids=a["affected_route_ids"],
            affected_stop_ids=a["affected_stop_ids"],
            start_time=a["start_time"],
            end_time=a["end_time"],
        )
        for a in alerts
    ]
