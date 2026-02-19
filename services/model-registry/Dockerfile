FROM python:3.11-slim

WORKDIR /app

COPY libs/common /app/libs/common
COPY libs/contracts /app/libs/contracts
COPY services/model-registry /app/services/model-registry

RUN pip install --no-cache-dir -U pip     && pip install --no-cache-dir -e /app/libs/common     && pip install --no-cache-dir -e /app/libs/contracts     && pip install --no-cache-dir fastapi "uvicorn[standard]" kafka-python

ENV PYTHONPATH=/app
WORKDIR /app/services/model-registry

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
