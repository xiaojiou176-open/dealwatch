FROM ghcr.io/astral-sh/uv:0.11.8@sha256:3b7b60a81d3c57ef471703e5c83fd4aaa33abcd403596fb22ab07db85ae91347 AS uv
# Trivy's Dockerfile policy checks each stage, including throwaway carrier stages.
USER 65532:65532
FROM mcr.microsoft.com/playwright/python:v1.59.0-noble@sha256:d8d9811a0e7cfac967f0c2f55d12b739087ae4b0808577b794c2a29ed5124938 AS runtime

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
