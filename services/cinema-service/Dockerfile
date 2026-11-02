FROM python:3.11-slim AS api
WORKDIR /app/service
COPY packages/python-platform /tmp/python-platform
RUN pip install --no-cache-dir /tmp/python-platform
COPY services/cinema-service/ /app/service/
RUN pip install --no-cache-dir .
EXPOSE 8086
CMD ["uvicorn", "cinema_service.main:application", "--factory", "--host", "0.0.0.0", "--port", "8086", "--no-proxy-headers", "--no-access-log"]
