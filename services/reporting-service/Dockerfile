FROM python:3.11-slim AS api
WORKDIR /app/service
COPY packages/python-platform /tmp/python-platform
RUN pip install --no-cache-dir /tmp/python-platform
COPY services/reporting-service/ /app/service/
RUN pip install --no-cache-dir .
EXPOSE 8089
CMD ["uvicorn", "reporting_service.main:application", "--factory", "--host", "0.0.0.0", "--port", "8089", "--no-proxy-headers", "--no-access-log"]
