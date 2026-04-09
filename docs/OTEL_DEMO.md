# OTEL 示例链路说明

当前发行版内置一套最小的跨服务 OTEL 示例链路，用于验证 Tempo 是否成功接收调用链。

## 1. 启用方式

在 .env 中设置：

```bash
AIOPS_COMPOSE_PROFILES=analysis,demo
```

如果已经启用了其他模块，可直接把 demo 加入现有 profile 列表。

## 2. 组件说明

- demo-gateway：对外提供 checkout 接口，并调用下游订单服务
- demo-order：模拟订单预占库存逻辑
- Tempo：通过 OTLP HTTP 接收 trace

## 3. 触发示例链路

启动后执行：

```bash
./scripts/generate-demo-trace.sh
```

该脚本会调用 demo-gateway 的 checkout 接口 3 次，生成 demo-gateway -> demo-order 的跨服务 trace。

## 4. 访问地址

- Demo Gateway：http://<host>:18082/healthz
- Demo Order：http://<host>:18083/healthz

## 5. Grafana 查看建议

在 Grafana 中选择 Tempo 数据源，按 service.name 查询：

- demo-gateway
- demo-order

也可以用时间范围缩小到最近 5 分钟后再检索，以便更快定位刚生成的 trace。
