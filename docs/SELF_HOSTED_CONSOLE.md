# 自建前端控制台

## 目标

SLZ-DevOps 当前已经具备监控、日志、告警、AI 分析和 CMDB 基础服务，但主要用户界面仍以 Grafana 为主。为了把平台打造成可独立演进的“自建运维平台”，建议将前端控制台单独建设为一层业务界面。

本仓库已经新增独立前端目录 apps/console，作为自建控制台的起点。该控制台具备以下特征：

- 与 Grafana 分离，面向平台运营与管理场景
- 通过 HTTP API 对接 AI Engine、CMDB、Prometheus、Alertmanager、Loki
- 可单独本地开发，也可容器化部署
- 可随当前仓库一起打包成离线发行版

## 当前能力

当前控制台已经内置四类基础页面能力：

- 平台健康总览
- 事件中心基础视图
- 作业中心受控执行视图
- AI 异常检测演示
- 根因分析演示入口
- CMDB 服务清单、筛选与编辑视图

这部分不是替代 Grafana，而是补出“平台控制面”和“管理面”的第一层骨架。

## 本地开发

```bash
cd apps/console
npm install
npm run dev
```

默认开发端口为 14000。

## 容器化部署

在 .env 中配置：

```env
CONSOLE_PORT=14000
AIOPS_COMPOSE_PROFILES=analysis,console
```

然后启动：

```bash
./scripts/up.sh
```

访问地址：

- 控制台：http://<host>:14000

## 后续演进建议

下一阶段建议把前端继续拆成以下几个业务域：

- 事件中心：告警收敛、升级、抑制、值班与通知编排
- CMDB 管理：服务、应用、主机、依赖关系和变更记录维护
- 作业中心：脚本执行、批量变更、回滚、审计追踪
- 诊断中心：异常分析、根因推理、链路影响面展示
- 资产与租户：账号、角色、权限、环境隔离与菜单配置

如果后续希望进一步产品化，建议把 apps/console 与 Python 服务一起升级为完整的前后端分层结构：

- apps/console: 前端控制台
- services/api-gateway: BFF 或统一 API 网关
- services/ai-engine: 智能分析服务
- services/cmdb: 资产与拓扑服务
- services/job-runner: 自动化作业与执行服务

这样可以逐步从“监控发行版”演进为“自建运维平台”。