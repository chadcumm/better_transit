FROM public.ecr.aws/lambda/python:3.12 AS build

# Install build tools — gcc-c++ is needed for greenlet C++ extensions
RUN dnf install -y git gcc gcc-c++ && dnf clean all

COPY requirements.txt ${LAMBDA_TASK_ROOT}/requirements.txt

RUN --mount=from=ghcr.io/astral-sh/uv,source=/uv,target=/bin/uv \
    uv pip install -r requirements.txt --target ${LAMBDA_TASK_ROOT} --system --compile-bytecode

FROM public.ecr.aws/lambda/python:3.12

COPY --from=build ${LAMBDA_TASK_ROOT} ${LAMBDA_TASK_ROOT}

COPY . ${LAMBDA_TASK_ROOT}

# SST sets the handler to api.src.better_transit.handler.handler based on the
# file path, but stages api/ contents at root. Create the api/src path with a
# symlink so the Lambda handler import resolves correctly.
RUN mkdir -p ${LAMBDA_TASK_ROOT}/api/src && \
    touch ${LAMBDA_TASK_ROOT}/api/__init__.py \
          ${LAMBDA_TASK_ROOT}/api/src/__init__.py && \
    ln -s ${LAMBDA_TASK_ROOT}/src/better_transit ${LAMBDA_TASK_ROOT}/api/src/better_transit

# Add src/ to Python path so "from better_transit..." imports work
ENV PYTHONPATH="${LAMBDA_TASK_ROOT}/src"
