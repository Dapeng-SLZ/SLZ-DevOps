# 中间件监控接入说明

当前发行版已支持以可选 profile 方式接入 Nginx、MySQL、Redis 和 SNMP 监控模块。

## 1. 启用方式

在 .env 中设置：

```bash
AIOPS_COMPOSE_PROFILES=middleware,network
```

只启用中间件模块时可设置为：

```bash
AIOPS_COMPOSE_PROFILES=middleware
```

## 2. 参数说明

- NGINX_STATUS_URI：Nginx stub_status 地址
- MYSQL_EXPORTER_DSN：MySQL exporter 使用的 DSN
- REDIS_EXPORTER_ADDR：Redis 地址
- REDIS_EXPORTER_PASSWORD：Redis 密码

## 3. Prometheus 目标文件

Prometheus 使用 file_sd 方式发现中间件 exporter 和 SNMP 目标。请将 example 文件内容复制到对应的 yml 文件中：

- deploy/prometheus/targets/nginx-exporter.example.yml -> deploy/prometheus/targets/nginx-exporter.yml
- deploy/prometheus/targets/mysqld-exporter.example.yml -> deploy/prometheus/targets/mysqld-exporter.yml
- deploy/prometheus/targets/redis-exporter.example.yml -> deploy/prometheus/targets/redis-exporter.yml
- deploy/prometheus/targets/snmp-targets.example.yml -> deploy/prometheus/targets/snmp-targets.yml

默认已附带中间件告警规则文件 [deploy/prometheus/rules/middleware-alerts.yml](deploy/prometheus/rules/middleware-alerts.yml) 和 Grafana 看板 [deploy/grafana/dashboards/middleware-overview.json](deploy/grafana/dashboards/middleware-overview.json)。

## 4. Nginx 要求

需要启用 stub_status，例如：

```nginx
location /stub_status {
    stub_status;
    allow 127.0.0.1;
    allow <docker_or_podman_network>;
    deny all;
}
```

## 5. MySQL 要求

建议创建只读 exporter 用户，并授予 PROCESS、REPLICATION CLIENT、SELECT 权限。

## 6. Redis 要求

如果 Redis 启用了密码，请同步配置 REDIS_EXPORTER_PASSWORD。

## 7. SNMP 要求

默认提供 public v2 示例认证与 if_mib 模块，生产环境应修改 community，并根据设备厂商生成正式 snmp.yml。
