#!/usr/bin/env bash
# Grundinstallation der VIN-Decoder-VM (Ubuntu 24.04).
# Idempotent: ein zweiter Lauf aendert nichts, was schon stimmt.
set -euo pipefail

log() { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }

export DEBIAN_FRONTEND=noninteractive

log "Paketquellen aktualisieren"
apt-get update -qq
apt-get upgrade -y -qq

log "Basiswerkzeuge"
apt-get install -y -qq \
    ca-certificates curl gnupg git jq rsync postgresql-client-16 unattended-upgrades

log "Docker-Repository einrichten"
install -m 0755 -d /etc/apt/keyrings
if [ ! -f /etc/apt/keyrings/docker.asc ]; then
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
fi
cat > /etc/apt/sources.list.d/docker.list <<EOF
deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable
EOF

log "Docker installieren"
apt-get update -qq
apt-get install -y -qq \
    docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

systemctl enable --now docker

log "Log-Rotation fuer Container"
cat > /etc/docker/daemon.json <<'EOF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF
systemctl restart docker

log "Projektverzeichnis"
mkdir -p /opt/vin-decoder
chmod 750 /opt/vin-decoder

log "Automatische Sicherheitsupdates"
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF

log "Fertig"
docker --version
docker compose version
