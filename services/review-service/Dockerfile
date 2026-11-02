FROM python:3.11-slim AS api
WORKDIR /app/service
COPY packages/python-platform /tmp/python-platform
RUN pip install --no-cache-dir /tmp/python-platform
COPY services/review-service/ /app/service/
RUN pip install --no-cache-dir .
EXPOSE 8083
CMD ["uvicorn", "review_service.main:application", "--factory", "--host", "0.0.0.0", "--port", "8083", "--no-proxy-headers", "--no-access-log"]

FROM api AS worker
RUN pip install --no-cache-dir ".[inference]"
CMD ["python", "-m", "review_service.worker"]
