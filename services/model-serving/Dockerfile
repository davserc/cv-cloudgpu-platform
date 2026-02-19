FROM python:3.11-slim

WORKDIR /app

COPY libs/common /app/libs/common
COPY services/model-serving /app/services/model-serving

RUN apt-get update     && apt-get install -y --no-install-recommends git libglib2.0-0 libgl1 libsm6 libxext6 libxrender1 libx11-6 libxcb1     && rm -rf /var/lib/apt/lists/*     && pip install --no-cache-dir -U pip     && pip install --no-cache-dir -e /app/libs/common     && pip install --no-cache-dir fastapi "uvicorn[standard]" ultralytics google-cloud-storage pillow numpy kafka-python     && mkdir -p /data/ultralytics     && chmod 777 /data/ultralytics

ENV PYTHONPATH=/app
ENV YOLO_CONFIG_DIR=/data/ultralytics
WORKDIR /app/services/model-serving

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
