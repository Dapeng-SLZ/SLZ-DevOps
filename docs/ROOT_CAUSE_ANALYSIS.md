# 根因分析底座说明

当前发行版已具备根因分析基础组件，但仍属于一期能力：

- CMDB：提供静态服务清单和依赖关系
- Neo4j：提供后续图关系持久化空间
- Tempo：提供调用链查询入口
- AI Engine：提供基于告警、拓扑和变更信息的启发式根因分析接口，并可自动从 CMDB 拉取拓扑

## 1. 启用方式

在 .env 中设置：

```bash
AIOPS_COMPOSE_PROFILES=analysis
```

如果需要同时启用中间件和分析层：

```bash
AIOPS_COMPOSE_PROFILES=middleware,network,analysis
```

## 2. 默认访问地址

- CMDB：http://<host>:18081
- Neo4j HTTP：http://<host>:17474
- Neo4j Bolt：http://<host>:17687
- Tempo：http://<host>:13200

## 3. CMDB 数据

示例 CMDB 数据位于 [services/cmdb/data/seed.json](services/cmdb/data/seed.json)，当前内置了 gateway、order-service、user-service、mysql-primary、redis-cache 的依赖关系。

## 4. AI 根因分析接口

接口路径：`POST /api/v1/root-cause/analyze`

如果请求中未传 `topology_edges`，AI Engine 会自动从 CMDB 的 `/api/v1/topology/edges` 拉取依赖关系补全分析。

示例请求：

```json
{
  "alerts": [
    {"source": "order-service", "severity": "critical", "summary": "order-service 5xx 增长"},
    {"source": "mysql-primary", "severity": "warning", "summary": "MySQL 连接数过高"}
  ],
  "impacted_services": ["gateway"],
  "topology_edges": [
    {"source": "gateway", "target": "order-service"},
    {"source": "order-service", "target": "mysql-primary"}
  ],
  "recent_changes": ["order-service deployment rollout at 10:21"]
}
```

## 5. 当前限制

- 根因分析仍为启发式规则，不是图算法或 LLM 推理。
- CMDB 仍为静态文件，不包含自动发现、审批和生命周期管理。
- Neo4j 目前通过脚本手动同步 CMDB 数据，尚未实现自动写入。
- Tempo 已接入 Grafana 数据源，但未内置 OTEL SDK 示例。

## 6. Neo4j 拓扑同步

启动 analysis profile 后，可执行：

```bash
./scripts/sync-cmdb-to-neo4j.sh
```

该脚本会从 CMDB 拉取 Cypher 并导入 Neo4j，便于后续图查询和知识图谱扩展。
