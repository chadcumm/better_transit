ARG PYTHON_VERSION=3.11
ARG PYTHON_RUNTIME

FROM public.ecr.aws/lambda/python:${PYTHON_VERSION} AS build

# Install build tools — gcc-c++ is needed for greenlet C++ extensions
RUN if [[ "$PYTHON_RUNTIME" == 3.1[2-9]* ]]; then \
    dnf install -y git gcc gcc-c++; \
else \
    yum install -y git gcc gcc-c++; \
fi

COPY requirements.txt ${LAMBDA_TASK_ROOT}/requirements.txt

RUN --mount=from=ghcr.io/astral-sh/uv,source=/uv,target=/bin/uv \
    uv pip install -r requirements.txt --target ${LAMBDA_TASK_ROOT} --system --compile-bytecode

FROM public.ecr.aws/lambda/python:${PYTHON_VERSION}

COPY --from=build ${LAMBDA_TASK_ROOT} ${LAMBDA_TASK_ROOT}

COPY . ${LAMBDA_TASK_ROOT}
