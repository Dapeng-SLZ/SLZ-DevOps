# openEuler 24.03 LTS SP3 部署说明

## 1. 目标环境

- 操作系统：openEuler 24.03 LTS SP3
- 最低规格：4 vCPU / 8 GB RAM / 100 GB SSD
- 网络要求：允许 13000、18080、19090、19093、19115 端口访问

## 2. 安装步骤

1. 将仓库同步到目标主机，例如 /opt/slz-devops/current。
2. 执行 scripts/install-openeuler.sh 完成基础依赖安装。
3. 复制 .env.example 为 .env，并按环境修改密码和端口。
4. 执行 scripts/up.sh 启动整个平台。
5. 执行 scripts/post-deploy-check.sh 完成启动后连通性检查。
6. 访问 Grafana、Prometheus、Alertmanager 和 AI Engine 健康接口完成验证。

在 openEuler + Podman 场景下，scripts/up.sh 会自动修正 data 目录写权限，避免 Prometheus 与 Loki 因挂载目录不可写而退出。

如果目标主机无法拉取 docker.io 镜像，可先执行 scripts/configure-container-mirrors.sh，为 Podman 写入镜像源配置，再手工验证 `podman pull python:3.12-slim`。

如果容器内部健康检查正常，但宿主机访问 13000、19090、19093、13100 等映射端口持续超时，可执行 scripts/fix-podman-network.sh。该脚本会将 Podman 网络后端切换为 netavark，并清理旧的 cni 网络状态。

如果 Podman 在 Python 服务镜像构建阶段出现 `pip` 域名解析失败，scripts/up.sh 会自动调用 scripts/build-python-images.sh，通过宿主机网络预构建 Python 服务镜像，再执行 compose 启动。

如需接入中间件监控，请在 .env 中配置 AIOPS_COMPOSE_PROFILES=middleware 或 AIOPS_COMPOSE_PROFILES=middleware,network，并参考 docs/MIDDLEWARE_MONITORING.md 补齐 exporter 参数与 Prometheus 目标文件。

如需启用根因分析底座，请在 .env 中加入 analysis profile，并在组件启动后执行 scripts/sync-cmdb-to-neo4j.sh 将 CMDB 拓扑同步到 Neo4j。

如需验证调用链追踪，请在 .env 中加入 demo profile，并在组件启动后执行 scripts/generate-demo-trace.sh 生成示例 trace。

## 3. 默认访问地址

- Grafana：http://<host>:13000
- Prometheus：http://<host>:19090
- Alertmanager：http://<host>:19093
- AI Engine：http://<host>:18080/healthz
- Blackbox Exporter：http://<host>:19115

## 4. 自动化部署

可使用 automation/ansible/playbooks/bootstrap-openeuler.yml 初始化节点，再使用 automation/ansible/playbooks/deploy-platform.yml 发布平台。

## 5. systemd 托管

执行 scripts/install-systemd-service.sh 可将平台注册为 systemd 服务，并启用开机自启动。

## 6. 发行包制作

执行 scripts/package-release.sh 可在 releases 目录下生成 tar.gz 发行包，适合离线交付或版本归档。

如果在 Windows 11 PowerShell 环境打包，可执行 scripts/package-release.ps1，生成 zip 发行包后再上传到 GitHub Release 或拷贝到 Linux 主机。

仓库已提供 GitHub Actions 自动发布流程 .github/workflows/release.yml。推送与 VERSION 一致的 tag 后，可自动生成 Linux 和 Windows 发行包并发布到 GitHub Release。

## 7. 生产建议

- 将 .env 中默认密码替换为强口令。
- Prometheus、Loki、Grafana 数据目录挂载到独立磁盘。
- 增加对象存储或远端时序存储，避免单机持久化瓶颈。
- 将 AI Engine 接入企业微信、钉钉或工单系统 webhook。
