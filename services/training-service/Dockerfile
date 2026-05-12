FROM python:3.11-slim

ARG CLOUDGPU_GIT_TOKEN

WORKDIR /app

COPY cv-cloudgpu-platform/libs/common /app/libs/common
COPY cv-cloudgpu-platform/libs/contracts /app/libs/contracts
COPY cv-cloudgpu-platform/services/training-service /app/services/training-service
COPY cloudgpu-automation-lib /app/cloudgpu-automation-lib

RUN apt-get update \
    && apt-get install -y --no-install-recommends git openssh-client \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -U pip \
    && pip install --no-cache-dir -e /app/libs/common \
    && pip install --no-cache-dir -e /app/libs/contracts \
    && pip install --no-cache-dir fastapi "uvicorn[standard]" kafka-python google-cloud-storage \
    && pip install --no-cache-dir -e /app/cloudgpu-automation-lib
ENV PYTHONPATH=/app
WORKDIR /app/services/training-service

COPY cv-cloudgpu-platform/services/training-service/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]


