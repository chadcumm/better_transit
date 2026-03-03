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
RUN echo "=== LAMBDA_TASK_ROOT top ===" && ls -la ${LAMBDA_TASK_ROOT}/ && \
    echo "=== src/ ===" && ls -la ${LAMBDA_TASK_ROOT}/src/ 2>/dev/null || echo "NO src/ dir" && \
    echo "=== better_transit/ ===" && ls -la ${LAMBDA_TASK_ROOT}/src/better_transit/ 2>/dev/null || echo "NO src/better_transit/ dir" && \
    echo "=== better_transit top-level? ===" && ls -la ${LAMBDA_TASK_ROOT}/better_transit/ 2>/dev/null || echo "NO better_transit/ at root"
