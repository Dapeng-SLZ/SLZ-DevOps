# 架构说明

## 1. 架构定位

本发行版不是单纯的监控工具集合，而是一个面向 openEuler 24.03 LTS SP3 的 AIOps 平台基础底座。它把观测、告警、分析、自动化四部分先串成一个可运行闭环，再逐步扩展到知识图谱、CMDB、容量预测和自愈执行。

## 2. 组件边界

- Prometheus：负责采集平台指标与规则告警。
- Alertmanager：负责告警路由与聚合。
- Grafana：负责统一展示。
- Loki + Promtail：负责日志聚合。
- Blackbox Exporter：负责基础探测。
- Node Exporter：负责主机资源采集。
- AIOps Engine：负责分析接口、Webhook 汇聚与后续 AI 扩展。

## 3. 落地原则

- 优先单机可用，再逐步走向多节点与高可用。
- 优先开源基础设施，降低首期交付复杂度。
- 优先兼容 openEuler 默认系统能力，减少额外依赖。
- 优先通过容器化和脚本化降低实施门槛。

## 4. 后续扩展建议

- 在 deploy 目录下新增 mysql、redis、snmp、tempo、neo4j、cmdb 子模块。
- 将 AI Engine 拆分为 detection、correlation、remediation 三个服务。
- 把脚本交付升级为 RPM 包或离线安装包，形成正式发行件。
