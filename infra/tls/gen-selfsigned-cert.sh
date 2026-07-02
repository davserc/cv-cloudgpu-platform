#!/usr/bin/env bash
# Genera un certificado TLS autofirmado (cert + key) para un servicio dado.
#
# Uso:
#   ./gen-selfsigned-cert.sh <name> <cn> [san1,san2,...]
#
# Ejemplo:
#   ./gen-selfsigned-cert.sh api-gateway api-gateway.cv-platform.svc.cluster.local \
#       "DNS:api-gateway,DNS:localhost,IP:34.45.21.197,IP:127.0.0.1"
#
# Los .crt/.key generados quedan en infra/tls/certs/ (excluido de git por *.crt/*.key
# en .gitignore). No es un certificado de una CA confiable — sirve para cifrar el
# transporte en tránsito mientras no haya un dominio propio para un cert real
# (Let's Encrypt / Google-managed). Ver README > Seguridad.
set -euo pipefail

NAME="${1:?Uso: gen-selfsigned-cert.sh <name> <cn> [sans]}"
CN="${2:?Falta el Common Name (CN)}"
SAN="${3:-DNS:${CN},DNS:localhost,IP:127.0.0.1}"

OUT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/certs"
mkdir -p "$OUT_DIR"

CRT="$OUT_DIR/${NAME}.crt"
KEY="$OUT_DIR/${NAME}.key"

openssl req -x509 -nodes -newkey rsa:2048 \
  -keyout "$KEY" \
  -out "$CRT" \
  -days 825 \
  -subj "//CN=${CN}" \
  -addext "subjectAltName=${SAN}"

echo "Generado:"
echo "  cert: $CRT"
echo "  key:  $KEY"
echo
echo "Para crear/actualizar el Secret en el cluster:"
echo "  kubectl create secret tls ${NAME}-tls --cert=\"$CRT\" --key=\"$KEY\" -n cv-platform --dry-run=client -o yaml | kubectl apply -f -"
