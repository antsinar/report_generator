ARG PYTHON_VERSION=3.12.4-slim-bullseye

FROM python:${PYTHON_VERSION} as python

FROM python as builder

RUN apt-get update && apt-get install --no-install-recommends -y \
    build-essential

COPY ./requirements.txt ./requirements.txt

RUN pip wheel --wheel-dir /usr/src/app/wheels \
    -r requirements.txt


FROM python as runner
ARG BUILD_ENVIRONMENT=prod
ARG APP_HOME=/app

ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1
ENV BUILD_ENV ${BUILD_ENVIRONMENT}

WORKDIR ${APP_HOME}

RUN apt-get update && apt-get install --no-install-recommends -y \
    # libpango-1.0-0 \
    # libpangoft2-1.0-0 \
    pango1.0-tools \
    && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/src/app/wheels /wheels/

RUN pip install --no-cache-dir --no-index --find-links=/wheels/ /wheels/* \
    && rm -rf /wheels/

EXPOSE 8080

COPY . ${APP_HOME}

CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8080"]