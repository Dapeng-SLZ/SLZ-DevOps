#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "请使用 root 用户执行。" >&2
  exit 1
fi

dnf makecache
dnf install -y git curl wget tar podman python3 python3-pip firewalld rsync

if ! command -v netavark >/dev/null 2>&1; then
  dnf install -y netavark
fi

if ! command -v aardvark-dns >/dev/null 2>&1; then
  dnf install -y aardvark-dns || echo "警告: 仓库中未找到 aardvark-dns，继续安装。若后续容器间服务名解析异常，请补充 DNS 组件。"
fi

if ! dnf install -y podman-compose; then
  echo "dnf 未提供 podman-compose，改用 pip 安装。"
  python3 -m pip install --upgrade pip
  python3 -m pip install podman-compose
fi

if ! command -v podman-compose >/dev/null 2>&1 && ! podman compose version >/dev/null 2>&1; then
  echo "未安装可用的 compose 运行时，请检查 podman / podman-compose 安装结果。" >&2
  exit 1
fi

systemctl enable --now firewalld
systemctl enable --now podman.socket || true

mkdir -p /etc/containers
cat >/etc/containers/containers.conf <<'EOF'
[network]
network_backend = "netavark"
EOF

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
