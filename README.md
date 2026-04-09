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

### 5. 验证服务

```bash
./scripts/validate-host.sh
curl http://127.0.0.1:18080/healthz
```

### 6. 配置开机自启

```bash
sudo ./scripts/install-systemd-service.sh
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

输出文件位于 releases 目录，命名格式为 slz-devops-<version>.tar.gz。

## 已实现范围

- 单机版基础观测与告警闭环
- openEuler 环境初始化脚本
- 启动前预检、启动后检查、自启动托管脚本
- 容器化发行版目录结构
- Grafana 数据源与基础看板预置
- AI 引擎最小分析服务
- Ansible 发布骨架
- 离线发行打包脚本

## 下一阶段建议

- 接入 VictoriaMetrics、Tempo、Neo4j、CMDB 服务
- 将 Alertmanager 路由扩展到企业微信、钉钉、邮件和工单系统
- 增加 Nginx、MySQL、Redis、SNMP Exporter 模块化配置
- 为 AI 引擎补充特征存储、根因推理和自愈执行编排

## 文档

- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
- [docs/MIDDLEWARE_MONITORING.md](docs/MIDDLEWARE_MONITORING.md)
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)


