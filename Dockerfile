# Reproduction container (PRD M5). Pinned interpreter and lockfile.
FROM python:3.12.7-slim
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.8.22 /uv /usr/local/bin/uv
WORKDIR /work
COPY . .
RUN uv sync --locked --python 3.12
# Provenance checks need a clean git tree; the image carries the repository's .git.
ENTRYPOINT ["uv", "run", "asaudit"]
CMD ["reproduce", "--paper", "--fixture"]
