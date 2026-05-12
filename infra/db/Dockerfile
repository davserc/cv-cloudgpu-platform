FROM python:3.11-slim
RUN pip install --no-cache-dir alembic sqlalchemy psycopg2-binary
COPY libs/common /workspace/libs/common
COPY infra/db /workspace/infra/db
WORKDIR /workspace
