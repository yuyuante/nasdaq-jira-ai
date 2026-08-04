FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY config ./config
COPY storage_state.json ./storage_state.json
RUN pip install --no-cache-dir . \
    && playwright install --with-deps chromium

RUN mkdir -p /app/data /app/logs
CMD ["nasdaq-jira", "--config", "config/config.example.yaml"]

