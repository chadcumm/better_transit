from pydantic import BaseModel


class AlertResponse(BaseModel):
    alert_id: str
    header: str
    description: str | None = None
    severity: str | None = None
    affected_route_ids: list[str] = []
    affected_stop_ids: list[str] = []
    start_time: str | None = None
    end_time: str | None = None
