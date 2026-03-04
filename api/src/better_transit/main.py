from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from better_transit.routes.alerts import router as alerts_router
from better_transit.routes.routes import router as routes_router
from better_transit.routes.stops import router as stops_router
from better_transit.routes.trips import router as trips_router

app = FastAPI(title="Better Transit", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stops_router)
app.include_router(routes_router)
app.include_router(trips_router)
app.include_router(alerts_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
