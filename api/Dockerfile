FROM public.ecr.aws/lambda/python:3.12

# Install system dependencies for geoalchemy2/shapely
RUN dnf install -y geos geos-devel proj proj-devel && dnf clean all

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:0.6 /uv /usr/local/bin/uv

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Install production dependencies only (no dev deps)
RUN uv sync --frozen --no-dev --no-install-project

# Copy application source
COPY src/ src/

# Install the project itself
RUN uv sync --frozen --no-dev

# Set the Lambda handler
CMD ["better_transit.handler.handler"]
