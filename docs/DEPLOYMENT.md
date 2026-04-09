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

如需接入中间件监控，请在 .env 中配置 AIOPS_COMPOSE_PROFILES=middleware 或 AIOPS_COMPOSE_PROFILES=middleware,network，并参考 docs/MIDDLEWARE_MONITORING.md 补齐 exporter 参数与 Prometheus 目标文件。

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

## 7. 生产建议

- 将 .env 中默认密码替换为强口令。
- Prometheus、Loki、Grafana 数据目录挂载到独立磁盘。
- 增加对象存储或远端时序存储，避免单机持久化瓶颈。
- 将 AI Engine 接入企业微信、钉钉或工单系统 webhook。
