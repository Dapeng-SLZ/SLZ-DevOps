#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "请使用 root 用户执行。" >&2
  exit 1
fi

dnf makecache
dnf install -y git curl wget tar podman podman-compose python3 python3-pip firewalld rsync

systemctl enable --now firewalld
systemctl enable --now podman.socket || true

mkdir -p /opt/slz-devops/{data,logs,releases}
mkdir -p /opt/slz-devops/current

cat >/etc/sysctl.d/99-slz-aiops.conf <<'EOF'
fs.inotify.max_user_instances = 1024
fs.inotify.max_user_watches = 524288
vm.max_map_count = 262144
EOF

sysctl --system

firewall-cmd --permanent --add-port=13000/tcp
firewall-cmd --permanent --add-port=18080/tcp
firewall-cmd --permanent --add-port=19090/tcp
firewall-cmd --permanent --add-port=19093/tcp
firewall-cmd --permanent --add-port=19115/tcp
firewall-cmd --reload

echo "如需开机自启，可在完成项目同步后执行:"
echo "  cp packaging/systemd/slz-aiops.service /etc/systemd/system/"
echo "  systemctl daemon-reload && systemctl enable --now slz-aiops"
echo "openEuler 24.03 LTS SP3 基础环境初始化完成。"
