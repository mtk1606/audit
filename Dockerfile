# Reproduction container (PRD M5). Pinned interpreter, pinned uv, locked dependencies.
# The full image already includes git (needed for run provenance), so the build
# needs no OS package installs: fewer network dependencies, at the cost of size.
FROM python:3.12.7-bookworm
# uv from PyPI (same version as CI) avoids a second registry dependency.
RUN pip install --no-cache-dir uv==0.8.22
WORKDIR /work
COPY . .
RUN uv sync --locked --python 3.12 \
    && git config --global --add safe.directory /work
# Provenance checks need a clean git tree; the image carries the repository's .git.
ENTRYPOINT ["uv", "run", "asaudit"]
CMD ["reproduce", "--paper", "--fixture"]
