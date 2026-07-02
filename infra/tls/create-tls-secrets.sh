#!/usr/bin/env bash
# Genera certificados autofirmados para api-gateway y grafana, y crea/actualiza
# los Secrets TLS correspondientes en el namespace cv-platform del cluster
# actualmente seleccionado por kubectl (revisar `kubectl config current-context`
# antes de correr esto).
#
# Si cambia la IP del LoadBalancer de alguno de los dos servicios, volver a
# correr este script para regenerar el cert con el SAN actualizado.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

API_GATEWAY_IP="${API_GATEWAY_LB_IP:-34.45.21.197}"
GRAFANA_IP="${GRAFANA_LB_IP:-}"

GATEWAY_SAN="DNS:api-gateway,DNS:api-gateway.cv-platform.svc.cluster.local,DNS:localhost,IP:127.0.0.1,IP:${API_GATEWAY_IP}"
GRAFANA_SAN="DNS:grafana,DNS:grafana.cv-platform.svc.cluster.local,DNS:localhost,IP:127.0.0.1"
if [ -n "$GRAFANA_IP" ]; then
  GRAFANA_SAN="${GRAFANA_SAN},IP:${GRAFANA_IP}"
fi

"$SCRIPT_DIR/gen-selfsigned-cert.sh" api-gateway api-gateway.cv-platform.svc.cluster.local "$GATEWAY_SAN"
"$SCRIPT_DIR/gen-selfsigned-cert.sh" grafana grafana.cv-platform.svc.cluster.local "$GRAFANA_SAN"

kubectl create secret tls api-gateway-tls \
  --cert="$SCRIPT_DIR/certs/api-gateway.crt" --key="$SCRIPT_DIR/certs/api-gateway.key" \
  -n cv-platform --dry-run=client -o yaml | kubectl apply -f -

kubectl create secret tls grafana-tls \
  --cert="$SCRIPT_DIR/certs/grafana.crt" --key="$SCRIPT_DIR/certs/grafana.key" \
  -n cv-platform --dry-run=client -o yaml | kubectl apply -f -

echo "Secrets api-gateway-tls y grafana-tls aplicados en namespace cv-platform."
echo "Reiniciar los deployments para que los sidecars TLS tomen el cert nuevo:"
echo "  kubectl rollout restart deployment/api-gateway deployment/grafana -n cv-platform"
