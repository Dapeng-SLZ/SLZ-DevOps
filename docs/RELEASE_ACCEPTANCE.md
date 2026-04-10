# 发布验收清单

## 版本范围

适用于当前 `0.2.0` 版本的单机自建平台验收。

当前版本重点能力包括：

- openEuler 默认部署与默认端口访问
- 独立前端控制台
- 事件中心最小闭环
- CMDB 基础维护能力
- 作业中心最小闭环
- 统一 SQLite 平台业务库
- 审计日志
- 数据库备份、恢复与 systemd 定时备份

## 一、部署验收

执行：

```bash
./scripts/up.sh
./scripts/post-deploy-check.sh
```

验收标准：

- `post-deploy-check.sh` 全部返回 `OK`
- 默认端口可访问：13000、18080、19090、19093、19115
- 启用 `analysis,console` profile 后，14000、18081、18084 可访问

## 二、控制台验收

访问 `http://<host>:14000`。

验收标准：

- 平台总览能显示核心组件健康状态
- 事件中心能展示事件列表
- 作业中心能展示作业模板与历史记录
- CMDB 区域能显示服务列表并支持筛选

## 三、事件中心验收

验收动作：

- 在控制台创建一条人工事件
- 对事件执行确认
- 对事件执行关闭

验收标准：

- 事件状态正确流转：`open -> acknowledged -> resolved`
- 服务重启后事件状态仍然存在

## 四、CMDB 验收

验收动作：

- 新增一个服务
- 修改该服务的负责人或层级
- 删除未被依赖的测试服务

验收标准：

- 变更后服务列表立即刷新
- 服务重启后数据仍然存在
- 删除被依赖服务时返回阻止信息

## 五、作业中心验收

验收动作：

- 执行“平台健康巡检”
- 执行“CMDB 拓扑导出”
- 执行“事件摘要报告”

验收标准：

- 作业状态从 `queued/running` 到 `succeeded/failed` 正常变化
- 控制台可查看结果摘要与日志
- 服务重启后执行记录仍然存在

## 六、审计验收

验收动作：

- 执行事件创建、事件确认、CMDB 编辑、作业运行

验收标准：

- 控制台“操作审计”区域能看到相应记录
- 记录中包含动作、资源类型、资源 ID、操作人、详情

## 七、备份恢复验收

执行：

```bash
./scripts/backup-platform-db.sh
ls data/backups/
./scripts/restore-platform-db.sh data/backups/platform-YYYYMMDD-HHMMSS.db
```

验收标准：

- 能成功生成平台数据库备份文件
- 恢复命令成功执行
- 恢复后事件、CMDB、作业记录仍可读取

## 八、systemd 验收

执行：

```bash
sudo ./scripts/install-systemd-service.sh
systemctl status slz-aiops.service --no-pager
systemctl status slz-platform-backup.timer --no-pager
systemctl list-timers | grep slz-platform-backup
```

验收标准：

- `slz-aiops.service` 已启用
- `slz-platform-backup.timer` 已启用
- 定时器下次执行时间可见

## 九、交付结论

若以上九项全部通过，可认为当前版本已经达到“单机自建平台最小可交付版”的发布标准。