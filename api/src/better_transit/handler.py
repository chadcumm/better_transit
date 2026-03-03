"""AWS Lambda handler — wraps the FastAPI app with Mangum."""

from mangum import Mangum

from better_transit.main import app

handler = Mangum(app, lifespan="off")
