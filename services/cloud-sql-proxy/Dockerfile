FROM gcr.io/cloud-sql-connectors/cloud-sql-proxy:2.9.0-alpine

COPY services/cloud-sql-proxy/entrypoint.sh /entrypoint.sh

ENTRYPOINT ["/bin/sh", "/entrypoint.sh"]
