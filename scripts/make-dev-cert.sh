#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CERT_DIR="$ROOT/.certs"

mkdir -p "$CERT_DIR"
cat > "$CERT_DIR/vkr-dev-ca.cnf" <<'EOF'
[req]
default_bits = 2048
prompt = no
default_md = sha256
x509_extensions = v3_ca
distinguished_name = dn

[dn]
CN = VKR Local Dev CA

[v3_ca]
basicConstraints = critical,CA:TRUE
keyUsage = critical,keyCertSign,cRLSign
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid:always,issuer
EOF

cat > "$CERT_DIR/vkr-dev.cnf" <<'EOF'
[req]
default_bits = 2048
prompt = no
default_md = sha256
req_extensions = v3_req
distinguished_name = dn

[dn]
CN = vkr-dev.local

[v3_req]
basicConstraints = critical,CA:FALSE
keyUsage = critical,digitalSignature,keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = localhost
DNS.2 = vkr-dev.local
DNS.3 = vkrinvent
IP.1 = 127.0.0.1
IP.2 = 192.168.157.249
EOF

cat > "$CERT_DIR/vkr-dev.ext" <<'EOF'
basicConstraints = critical,CA:FALSE
keyUsage = critical,digitalSignature,keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = localhost
DNS.2 = vkr-dev.local
DNS.3 = vkrinvent
IP.1 = 127.0.0.1
IP.2 = 192.168.157.249
EOF

openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
  -keyout "$CERT_DIR/vkr-dev-ca.key" \
  -out "$CERT_DIR/vkr-dev-ca.crt" \
  -config "$CERT_DIR/vkr-dev-ca.cnf"

openssl req -nodes -newkey rsa:2048 \
  -keyout "$CERT_DIR/vkr-dev.key" \
  -out "$CERT_DIR/vkr-dev.csr" \
  -config "$CERT_DIR/vkr-dev.cnf"

openssl x509 -req -days 825 \
  -in "$CERT_DIR/vkr-dev.csr" \
  -CA "$CERT_DIR/vkr-dev-ca.crt" \
  -CAkey "$CERT_DIR/vkr-dev-ca.key" \
  -CAcreateserial \
  -out "$CERT_DIR/vkr-dev.crt" \
  -extfile "$CERT_DIR/vkr-dev.ext"
