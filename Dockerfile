FROM ghcr.io/astral-sh/uv:0.11.5@sha256:555ac94f9a22e656fc5f2ce5dfee13b04e94d099e46bb8dd3a73ec7263f2e484 AS uv
# Trivy's Dockerfile policy checks each stage, including throwaway carrier stages.
USER 65532:65532
FROM mcr.microsoft.com/playwright/python:v1.58.0-noble@sha256:678457c4c323b981d8b4befc57b95366bb1bb6aa30057b1269f6b171e8d9975a AS runtime

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src
ENV PATH=/app/.venv/bin:$PATH
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

COPY --from=uv /uv /uvx /bin/
COPY pyproject.toml uv.lock /app/
RUN uv sync --frozen --no-dev --no-install-project

COPY . /app

RUN uv sync --frozen --no-dev --no-editable
RUN python -m playwright install chromium
RUN useradd --create-home --home-dir /home/dealwatch --shell /usr/sbin/nologin dealwatch \
    && chown -R dealwatch:dealwatch /app

USER dealwatch

CMD ["python", "-m", "dealwatch", "server"]
