FROM public.ecr.aws/lambda/python:3.12 AS build

# Install build tools — gcc-c++ is needed for greenlet C++ extensions
RUN dnf install -y git gcc gcc-c++ && dnf clean all

COPY requirements.txt ${LAMBDA_TASK_ROOT}/requirements.txt

RUN --mount=from=ghcr.io/astral-sh/uv,source=/uv,target=/bin/uv \
    uv pip install -r requirements.txt --target ${LAMBDA_TASK_ROOT} --system --compile-bytecode

FROM public.ecr.aws/lambda/python:3.12

COPY --from=build ${LAMBDA_TASK_ROOT} ${LAMBDA_TASK_ROOT}

COPY . ${LAMBDA_TASK_ROOT}

# Debug: show what SST staged in the build context
RUN echo "=== LAMBDA_TASK_ROOT contents ===" && \
    find ${LAMBDA_TASK_ROOT} -maxdepth 3 -type f | head -60 && \
    echo "=== directories ===" && \
    find ${LAMBDA_TASK_ROOT} -maxdepth 3 -type d | head -30
