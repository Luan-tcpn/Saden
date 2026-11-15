#!/usr/bin/env bash
# SADEN — preparação de servidor Ubuntu 24.04 LTS (executar como root, uma vez)
#
# O que faz: atualiza o sistema, instala Docker + Compose, cria usuário de
# deploy, aplica firewall (22/80/443), limita logs do Docker, configura fuso
# horário de São Paulo e atualizações de segurança automáticas.
#
# O que NÃO faz: abrir portas extras, instalar banco, criar contas, mexer em DNS.
#
# Revisar antes de executar:  less setup-server.sh
# Executar:                   sudo bash setup-server.sh

set -euo pipefail

DEPLOY_USER="${DEPLOY_USER:-saden}"
TIMEZONE="America/Sao_Paulo"

if [[ $EUID -ne 0 ]]; then
  echo "execute como root (sudo bash setup-server.sh)" >&2
  exit 1
fi

echo "== sistema =="
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get upgrade -y -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
  ca-certificates curl gnupg ufw unattended-upgrades fail2ban jq chrony

echo "== fuso horário =="
timedatectl set-timezone "$TIMEZONE"

echo "== usuário de deploy =="
if ! id "$DEPLOY_USER" >/dev/null 2>&1; then
  adduser --disabled-password --gecos "" "$DEPLOY_USER"
  usermod -aG sudo "$DEPLOY_USER"
  install -d -m 700 -o "$DEPLOY_USER" -g "$DEPLOY_USER" "/home/$DEPLOY_USER/.ssh"
  echo "  usuário $DEPLOY_USER criado. Copie sua chave pública para /home/$DEPLOY_USER/.ssh/authorized_keys ANTES de desativar senha."
fi

echo "== docker (repositório oficial) =="
if ! command -v docker >/dev/null 2>&1; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
usermod -aG docker "$DEPLOY_USER"

echo "== limites de log do docker =="
install -d -m 755 /etc/docker
cat >/etc/docker/daemon.json <<'JSON'
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "3" },
  "live-restore": true
}
JSON
systemctl restart docker

echo "== firewall (apenas SSH, HTTP e HTTPS) =="
ufw --force reset >/dev/null
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'ssh'
ufw allow 80/tcp comment 'http (redirect + ACME)'
ufw allow 443/tcp comment 'https'
ufw --force enable
ufw status verbose

echo "== atualizações de segurança automáticas =="
cat >/etc/apt/apt.conf.d/20auto-upgrades <<'CONF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
CONF

echo "== persistent journal =="
install -d -m 755 /var/log/journal
systemctl restart systemd-journald || true

echo "== diretório da aplicação =="
install -d -m 750 -o "$DEPLOY_USER" -g "$DEPLOY_USER" /srv/saden
echo "  /srv/saden criado (dono: $DEPLOY_USER)"

echo
echo "PRÓXIMOS PASSOS (manuais, com revisão):"
echo "  1. copiar a chave SSH e testar login como $DEPLOY_USER"
echo "  2. em /etc/ssh/sshd_config: PasswordAuthentication no; PermitRootLogin no"
echo "     systemctl reload ssh"
echo "  3. copiar deploy/ para /srv/saden/ e criar /srv/saden/.env (chmod 600)"
echo "  4. docker compose --env-file .env -f docker-compose.prod.yml up -d"
