FROM python:3.13-slim

# git is needed because clone_repo shells out to it
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# dependencies first — this layer caches, so code changes don't reinstall everything
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# then the code
COPY src/ ./src/
COPY README.md ./
RUN uv sync --frozen --no-dev


EXPOSE 8000

CMD ["uv", "run", "uvicorn", "cartograph.api:app", "--host", "0.0.0.0", "--port", "8000"]