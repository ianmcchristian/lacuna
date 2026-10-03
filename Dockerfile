# Weights: fetched and checksum-checked in their own stage
FROM python:3.12-slim AS weights
RUN pip install --no-cache-dir httpx
COPY scripts/download_weights.py /scripts/
RUN python /scripts/download_weights.py s

# Build: install locked deps into a venv. No PyTorch, just ONNX Runtime.
FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY README.md LICENSE ./
COPY lacuna ./lacuna
RUN uv sync --locked --no-dev --no-editable

# INT8 copy of the weights, calibrated on the hard-case shelves in docs/
FROM build AS quantize
RUN uv sync --locked --no-dev --no-editable --group quantize
COPY scripts/quantize.py ./scripts/
COPY docs/scenarios ./docs/scenarios
COPY --from=weights /models ./models
RUN .venv/bin/python scripts/quantize.py

# Runtime
FROM python:3.12-slim
RUN useradd --create-home --uid 1000 lacuna
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY --from=quantize /app/models /app/models
COPY alembic.ini ./
COPY migrations ./migrations
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    LACUNA_MODEL_PATH=models/sku110k-yolo11-s640-int8.onnx
USER lacuna
EXPOSE 8080
# Render sets PORT. Access logs come from the app as JSON, so uvicorn's are off.
CMD ["sh", "-c", "exec uvicorn lacuna.main:create_app --factory --host 0.0.0.0 --port ${PORT} --no-access-log"]
