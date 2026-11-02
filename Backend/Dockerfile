FROM python:3.11-slim

WORKDIR /app

# Cài dependency
COPY Backend/requirements.txt .
RUN pip install -r requirements.txt

# Copy source code
COPY packages/python-platform /tmp/python-platform
RUN pip install --no-cache-dir /tmp/python-platform
COPY Backend/ .

# Expose port
EXPOSE 8000

# Chạy migrations sau đó khởi động FastAPI
CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000"]
