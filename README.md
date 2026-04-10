# SLZ-DevOps

面向 openEuler 24.03 LTS SP3 的 AIOps 智能运维平台发行项目。当前仓库提供一套可落地的最小发行版骨架，目标是把“方案设计”推进到“可安装、可启动、可二次开发”的交付形态。

## 项目目标

- 基于 openEuler 24.03 LTS SP3 构建统一运维平台。
- 提供监控、日志、告警、自动化与智能分析的基础闭环。
- 兼容 Docker Compose 或 Podman Compose 部署方式。
- 预留 Ansible 自动化发布与后续扩展能力。

## 当前发行版内容

```text
SLZ-DevOps/
├── automation/ansible/        # 节点初始化与平台发布 Playbook
├── deploy/
│   ├── alertmanager/          # Alertmanager 配置
│   ├── blackbox/              # Blackbox Exporter 配置
│   ├── compose/               # 容器编排入口
│   ├── grafana/               # Grafana 数据源、看板预置
│   ├── loki/                  # Loki 配置
│   ├── prometheus/            # Prometheus 抓取与告警规则
│   └── promtail/              # Promtail 配置
├── docs/                      # 部署与交付文档
├── scripts/                   # openEuler 安装、启动、校验脚本
└── services/ai-engine/        # 最小可运行智能分析服务
```

## 架构组成

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ Grafana                                                                    │
│ 统一可视化、看板展示、数据源聚合                                           │
├─────────────────────────────────────────────────────────────────────────────┤
│ Prometheus + Alertmanager + AIOps Engine                                   │
│ 指标采集、规则告警、Webhook 汇聚、异常检测与事件关联                        │
├─────────────────────────────────────────────────────────────────────────────┤
│ Loki + Promtail + Blackbox Exporter + Node Exporter                        │
│ 日志采集、链路探测、主机指标、可观测性基础能力                              │
├─────────────────────────────────────────────────────────────────────────────┤
│ Ansible + Shell Scripts                                                    │
│ openEuler 初始化、发布、运维自动化                                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 快速开始

### 1. 目标主机要求

- 操作系统：openEuler 24.03 LTS SP3
- 建议资源：4 vCPU / 8 GB RAM / 100 GB SSD
- 运行时：Docker Compose 或 Podman Compose，推荐 openEuler 原生 Podman Compose

### 2. 安装基础依赖

```bash
chmod +x scripts/*.sh
sudo ./scripts/install-openeuler.sh
```

如果目标主机无法直接访问 Docker Hub，可先配置 Podman 镜像源：

```bash
sudo ./scripts/configure-container-mirrors.sh
podman pull python:3.12-slim
```

如果 openEuler + Podman 环境在 Python 服务镜像构建阶段出现 `pip` DNS 解析失败，`./scripts/up.sh` 会先调用 [scripts/build-python-images.sh](scripts/build-python-images.sh) 通过宿主机网络预构建 `ai-engine`、`cmdb`、`demo-*` 镜像，再由 compose 启动容器。

如果容器内部访问正常，但宿主机访问 `13000`、`19090` 等映射端口持续超时，请执行：

```bash
sudo ./scripts/fix-podman-network.sh
./scripts/up.sh
```

该脚本会把 Podman 网络后端从 `cni` 切换为 `netavark`，用于修复 openEuler 上宿主机端口映射异常的问题。

在 openEuler + Podman 默认部署场景下，`./scripts/up.sh` 会自动为默认端口 `13000/19090/19093/18080/...` 建立宿主机代理，因此保持 GitHub 源码默认端口不变即可访问，无需手工改端口。

### 3. 初始化环境文件

```bash
cp .env.example .env
vi .env
```

至少修改以下配置：

- Grafana 管理员账号密码
- 平台对外端口
- AI 引擎联动鉴权参数

### 4. 启动平台

```bash
./scripts/up.sh
./scripts/post-deploy-check.sh
```

在 openEuler + Podman 场景下，`up.sh` 会自动为 `data/` 下的持久化目录补齐写权限，避免 Prometheus、Loki、Grafana 等非 root 容器因无法写入挂载目录而启动失败。

### 5. 验证服务

```bash
./scripts/validate-host.sh
curl http://127.0.0.1:18080/healthz
```

### 6. 配置开机自启

```bash
sudo ./scripts/install-systemd-service.sh
```

### 7. 同步 CMDB 到 Neo4j

```bash
./scripts/sync-cmdb-to-neo4j.sh
```

### 8. 生成示例 Trace

```bash
./scripts/generate-demo-trace.sh
```

## 默认访问地址

- Grafana：http://<host>:13000
- Prometheus：http://<host>:19090
- Alertmanager：http://<host>:19093
- AI Engine：http://<host>:18080/healthz
- Blackbox Exporter：http://<host>:19115

## 智能分析服务能力

services/ai-engine 提供当前版本的最小能力闭环：

- 健康检查接口
- Prometheus 兼容指标接口
- 基于 Z-Score 的时序异常检测接口
- 告警事件聚合与初步关联分析接口
- Alertmanager Webhook 接收入口

这部分是后续接入 LLM、知识图谱、根因推理和自愈决策的基础控制面。

## 中间件监控扩展

当前已接入可选中间件监控模块：

- Nginx Exporter
- MySQL Exporter
- Redis Exporter
- SNMP Exporter

启用方式见 [docs/MIDDLEWARE_MONITORING.md](docs/MIDDLEWARE_MONITORING.md)。

## 根因分析底座

当前已补充分析层基础组件：

- CMDB 服务
- Neo4j 图数据库
- Grafana Tempo 链路存储
- AI 引擎根因分析接口

启用 `analysis` profile 后，可作为后续拓扑推理、链路关联和故障传播分析的基础。 

## OTEL 示例链路

当前已内置 demo-gateway 和 demo-order 两个示例服务，可通过 OTLP 将跨服务 trace 写入 Tempo，用于本地验证链路追踪能力。

启用方式见 [docs/OTEL_DEMO.md](docs/OTEL_DEMO.md)。

## 自动化发布

可使用 Ansible 进行节点初始化与平台发布：

```bash
ansible-playbook -i automation/ansible/inventory/production.ini automation/ansible/playbooks/bootstrap-openeuler.yml
ansible-playbook -i automation/ansible/inventory/production.ini automation/ansible/playbooks/deploy-platform.yml
```

## 发行打包

可直接生成离线交付压缩包：

```bash
./scripts/package-release.sh
```

Windows PowerShell 环境可执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\package-release.ps1
```

输出文件位于 releases 目录：

- Linux 脚本输出 `slz-devops-<version>.tar.gz`
- Windows PowerShell 脚本输出 `slz-devops-<version>.zip`

## GitHub Actions 自动发布

仓库已提供 GitHub Actions 工作流 [release.yml](.github/workflows/release.yml)。

使用方式：

- 推送与 [VERSION](VERSION) 一致的 tag，例如 `v0.1.0`
- 或在 GitHub Actions 页面手动运行 `Release Packages`，并输入 tag

工作流会自动：

- 在 Ubuntu 上生成 `tar.gz` 发行包
- 在 Windows 上生成 `zip` 发行包
- 自动创建或更新 GitHub Release，并上传两个附件

## 常见问题

- 如果 `./scripts/up.sh` 卡在 `python:3.12-slim` 或其他镜像拉取阶段，通常是目标主机无法访问 `docker.io` 的 443 端口。先执行 [scripts/configure-container-mirrors.sh](scripts/configure-container-mirrors.sh)，再手工验证 `podman pull python:3.12-slim`。
- 如果容器内部 `wget http://127.0.0.1:3000/login`、`wget http://127.0.0.1:9090/-/healthy` 能返回，但宿主机 `curl http://127.0.0.1:13000`、`curl http://127.0.0.1:19090` 一直超时，优先检查 `podman info --format '{{.Host.NetworkBackend}}'` 是否为 `cni`。如是，执行 [scripts/fix-podman-network.sh](scripts/fix-podman-network.sh) 切换到 `netavark`。

## 已实现范围

- 单机版基础观测与告警闭环
- openEuler 环境初始化脚本
- 启动前预检、启动后检查、自启动托管脚本
- 容器化发行版目录结构
- Grafana 数据源与基础看板预置
- 中间件监控看板与默认告警规则
- CMDB、Neo4j、Tempo 与根因分析基础接口
- CMDB 与 AI 引擎自动拓扑联动
- OTEL 示例链路与 Tempo 验证路径
- AI 引擎最小分析服务
- Ansible 发布骨架
- 离线发行打包脚本

## 下一阶段建议

- 接入 VictoriaMetrics 和更长期存储方案
- 将 Alertmanager 路由扩展到企业微信、钉钉、邮件和工单系统
- 为 AI 引擎补充特征存储、图推理、LLM 分析和自愈执行编排
- 为 CMDB、Neo4j、Tempo 增加自动发现与数据写入链路

## 文档

- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
- [docs/MIDDLEWARE_MONITORING.md](docs/MIDDLEWARE_MONITORING.md)
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/ROOT_CAUSE_ANALYSIS.md](docs/ROOT_CAUSE_ANALYSIS.md)
- [docs/OTEL_DEMO.md](docs/OTEL_DEMO.md)



