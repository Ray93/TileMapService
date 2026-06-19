FROM python:3.14-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY pyproject.toml uv.lock* .python-version* ./
RUN pip install --no-cache-dir uv && uv sync --no-dev

COPY src/ ./src/
COPY config/ ./config/

EXPOSE 8000

CMD ["uv", "run", "python", "src/main.py", "--host", "0.0.0.0", "--port", "8000"]
