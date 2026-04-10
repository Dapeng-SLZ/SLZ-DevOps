import { startTransition, useDeferredValue, useEffect, useMemo, useState } from 'react';
import {
  acknowledgeEvent,
  analyzeRootCause,
  createManualEvent,
  createService,
  deleteService,
  detectAnomaly,
  fetchAuditLogs,
  fetchCurrentUser,
  fetchEvents,
  fetchJobs,
  fetchJobTemplates,
  fetchNavigation,
  fetchPlatformHealth,
  fetchTopology,
  fetchWorkspaceSummary,
  login,
  logout,
  resolveEvent,
  runJob,
  updateService,
} from './api';
import type {
  AnomalyResult,
  AuditListPayload,
  EventListPayload,
  JobListPayload,
  JobTemplate,
  NavigationGroup,
  RootCauseResult,
  ServiceHealth,
  ServiceRecord,
  TopologyPayload,
  UserProfile,
  WorkspaceSummary,
} from './types';

const defaultSeries = '21, 22, 23, 24, 22, 25, 48, 24, 23, 22';

const fallbackNavigation: NavigationGroup[] = [
  {
    title: '配置与资产',
    items: [
      { key: 'cmdb', label: 'CMDB', implemented: true },
      { key: 'host-center', label: '主机中心', implemented: true },
      { key: 'multi-cloud', label: '多云管理', implemented: false },
    ],
  },
  {
    title: '变更与执行',
    items: [
      { key: 'jobs', label: '任务中心', implemented: true },
      { key: 'tickets', label: '工单系统', implemented: false },
      { key: 'containers', label: '容器管理', implemented: false },
    ],
  },
  {
    title: '可观测与事件',
    items: [
      { key: 'overview', label: '平台总览', implemented: true },
      { key: 'observability', label: '可观测性', implemented: true },
      { key: 'events', label: '事件墙', implemented: true },
    ],
  },
  {
    title: '智能助手',
    items: [{ key: 'assistant', label: 'AIOps 助手', implemented: true }],
  },
];

function formatRelativeTime(timestamp: number | null): string {
  if (!timestamp) {
    return '未完成';
  }

  const delta = Date.now() / 1000 - timestamp;
  if (delta < 60) {
    return '刚刚';
  }
  if (delta < 3600) {
    return `${Math.floor(delta / 60)} 分钟前`;
  }
  if (delta < 86400) {
    return `${Math.floor(delta / 3600)} 小时前`;
  }
  return `${Math.floor(delta / 86400)} 天前`;
}

function formatTimestamp(timestamp: number): string {
  return new Date(timestamp * 1000).toLocaleString('zh-CN', {
    hour12: false,
  });
}

function App() {
  const [activeView, setActiveView] = useState('overview');
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(null);
  const [navigationGroups, setNavigationGroups] = useState<NavigationGroup[]>(fallbackNavigation);
  const [workspaceSummary, setWorkspaceSummary] = useState<WorkspaceSummary | null>(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [authError, setAuthError] = useState('');
  const [loginUsername, setLoginUsername] = useState('admin');
  const [loginPassword, setLoginPassword] = useState('Admin@123456');

  const [health, setHealth] = useState<ServiceHealth[]>([]);
  const [healthLoading, setHealthLoading] = useState(true);
  const [healthError, setHealthError] = useState('');

  const [seriesInput, setSeriesInput] = useState(defaultSeries);
  const [sensitivity, setSensitivity] = useState('2.6');
  const [anomalyResult, setAnomalyResult] = useState<AnomalyResult | null>(null);
  const [anomalyError, setAnomalyError] = useState('');

  const [rootCauseSource, setRootCauseSource] = useState('ai-engine');
  const [rootCauseSeverity, setRootCauseSeverity] = useState('critical');
  const [rootCauseSummary, setRootCauseSummary] = useState('AI Engine latency spikes with downstream timeout');
  const [impactedServices, setImpactedServices] = useState('prometheus,grafana');
  const [rootCauseResult, setRootCauseResult] = useState<RootCauseResult | null>(null);
  const [rootCauseError, setRootCauseError] = useState('');

  const [topology, setTopology] = useState<TopologyPayload | null>(null);
  const [topologyError, setTopologyError] = useState('');
  const [search, setSearch] = useState('');
  const [events, setEvents] = useState<EventListPayload | null>(null);
  const [eventsError, setEventsError] = useState('');
  const [manualEventSource, setManualEventSource] = useState('platform-console');
  const [manualEventSeverity, setManualEventSeverity] = useState('warning');
  const [manualEventSummary, setManualEventSummary] = useState('人工巡检发现异常，需要人工介入');
  const [serviceForm, setServiceForm] = useState<ServiceRecord>({
    id: 'svc-new',
    name: 'new-service',
    tier: 'app',
    owner: 'platform',
    criticality: 'medium',
    dependencies: [],
  });
  const [editingServiceId, setEditingServiceId] = useState('');
  const [serviceMutationError, setServiceMutationError] = useState('');
  const [jobTemplates, setJobTemplates] = useState<JobTemplate[]>([]);
  const [jobs, setJobs] = useState<JobListPayload | null>(null);
  const [jobsError, setJobsError] = useState('');
  const [auditLogs, setAuditLogs] = useState<AuditListPayload | null>(null);
  const [auditError, setAuditError] = useState('');
  const deferredSearch = useDeferredValue(search);

  async function refreshEvents() {
    try {
      const payload = await fetchEvents();
      startTransition(() => {
        setEvents(payload);
        setEventsError('');
      });
    } catch (error) {
      setEventsError(error instanceof Error ? error.message : '事件列表加载失败');
    }
  }

  async function refreshJobs() {
    try {
      const [templatesPayload, jobsPayload] = await Promise.all([fetchJobTemplates(), fetchJobs()]);
      startTransition(() => {
        setJobTemplates(templatesPayload.templates);
        setJobs(jobsPayload);
        setJobsError('');
      });
    } catch (error) {
      setJobsError(error instanceof Error ? error.message : '作业中心加载失败');
    }
  }

  async function refreshAuditLogs() {
    try {
      const payload = await fetchAuditLogs();
      startTransition(() => {
        setAuditLogs(payload);
        setAuditError('');
      });
    } catch (error) {
      setAuditError(error instanceof Error ? error.message : '审计日志加载失败');
    }
  }

  useEffect(() => {
    let cancelled = false;

    async function restoreSession() {
      try {
        const [mePayload, navigationPayload] = await Promise.all([fetchCurrentUser(), fetchNavigation()]);
        if (cancelled) {
          return;
        }
        startTransition(() => {
          setCurrentUser(mePayload.user);
          setNavigationGroups(navigationPayload.groups);
          setAuthError('');
          setAuthLoading(false);
        });
      } catch {
        if (cancelled) {
          return;
        }
        setAuthLoading(false);
      }
    }

    void restoreSession();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!currentUser) {
      return;
    }

    let cancelled = false;

    async function loadWorkspace() {
      try {
        const [summaryPayload, healthPayload, topologyPayload, eventsPayload, templatesPayload, jobsPayload, auditPayload] = await Promise.all([
          fetchWorkspaceSummary(),
          fetchPlatformHealth(),
          fetchTopology(),
          fetchEvents(),
          fetchJobTemplates(),
          fetchJobs(),
          fetchAuditLogs(),
        ]);

        if (cancelled) {
          return;
        }

        startTransition(() => {
          setWorkspaceSummary(summaryPayload);
          setHealth(healthPayload);
          setHealthError('');
          setHealthLoading(false);
          setTopology(topologyPayload);
          setTopologyError('');
          setEvents(eventsPayload);
          setEventsError('');
          setJobTemplates(templatesPayload.templates);
          setJobs(jobsPayload);
          setJobsError('');
          setAuditLogs(auditPayload);
          setAuditError('');
        });
      } catch (error) {
        if (cancelled) {
          return;
        }
        setHealthLoading(false);
        const message = error instanceof Error ? error.message : '工作台加载失败';
        setHealthError(message);
      }
    }

    void loadWorkspace();

    return () => {
      cancelled = true;
    };
  }, [currentUser]);

  const filteredServices = useMemo(() => {
    if (!topology) {
      return [];
    }

    const keyword = deferredSearch.trim().toLowerCase();
    if (!keyword) {
      return topology.services;
    }

    return topology.services.filter((service) => {
      return [service.name, service.owner, service.tier, service.criticality]
        .join(' ')
        .toLowerCase()
        .includes(keyword);
    });
  }, [deferredSearch, topology]);

  const healthyCount = health.filter((item) => item.status === 'healthy').length;
  const degradedServices = health.filter((item) => item.status !== 'healthy');
  const recentJobs = jobs?.jobs.slice(0, 4) ?? [];
  const recentAuditLogs = auditLogs?.items.slice(0, 5) ?? [];
  const priorityEvents = (events?.events ?? []).slice(0, 5);
  const serviceStats = useMemo(() => {
    const services = topology?.services ?? [];
    return {
      total: services.length,
      highCriticality: services.filter((service) => service.criticality === 'high').length,
      tiers: new Set(services.map((service) => service.tier)).size,
    };
  }, [topology]);

  function resetServiceForm() {
    setEditingServiceId('');
    setServiceForm({
      id: 'svc-new',
      name: 'new-service',
      tier: 'app',
      owner: 'platform',
      criticality: 'medium',
      dependencies: [],
    });
  }

  async function handleLogin(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAuthError('');

    try {
      const loginPayload = await login(loginUsername, loginPassword);
      const [navigationPayload, summaryPayload] = await Promise.all([fetchNavigation(), fetchWorkspaceSummary()]);
      startTransition(() => {
        setCurrentUser(loginPayload.user);
        setNavigationGroups(navigationPayload.groups);
        setWorkspaceSummary(summaryPayload);
      });
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : '登录失败');
    }
  }

  async function handleLogout() {
    try {
      await logout();
    } finally {
      setCurrentUser(null);
      setWorkspaceSummary(null);
      setAuthError('');
      setActiveView('overview');
    }
  }

  async function handleDetectAnomaly(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAnomalyError('');

    try {
      const values = seriesInput
        .split(',')
        .map((value) => Number(value.trim()))
        .filter((value) => !Number.isNaN(value));

      const result = await detectAnomaly(values, Number(sensitivity));
      setAnomalyResult(result);
    } catch (error) {
      setAnomalyError(error instanceof Error ? error.message : '异常检测失败');
    }
  }

  async function handleAnalyzeRootCause(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setRootCauseError('');

    try {
      const result = await analyzeRootCause({
        source: rootCauseSource,
        severity: rootCauseSeverity,
        summary: rootCauseSummary,
        impactedServices: impactedServices
          .split(',')
          .map((value) => value.trim())
          .filter(Boolean),
      });
      setRootCauseResult(result);
    } catch (error) {
      setRootCauseError(error instanceof Error ? error.message : '根因分析失败');
    }
  }

  async function handleCreateManualEvent(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setEventsError('');

    try {
      await createManualEvent({
        source: manualEventSource,
        severity: manualEventSeverity,
        summary: manualEventSummary,
      });
      await refreshEvents();
      await refreshAuditLogs();
    } catch (error) {
      setEventsError(error instanceof Error ? error.message : '人工事件创建失败');
    }
  }

  async function handleEventAction(eventId: string, action: 'ack' | 'resolve') {
    setEventsError('');

    try {
      if (action === 'ack') {
        await acknowledgeEvent(eventId, currentUser?.username ?? 'console-user');
      } else {
        await resolveEvent(eventId, currentUser?.username ?? 'console-user');
      }
      await refreshEvents();
      await refreshAuditLogs();
    } catch (error) {
      setEventsError(error instanceof Error ? error.message : '事件操作失败');
    }
  }

  async function handleSubmitService(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setServiceMutationError('');

    try {
      if (editingServiceId) {
        await updateService(editingServiceId, serviceForm);
      } else {
        await createService(serviceForm);
      }
      const payload = await fetchTopology();
      setTopology(payload);
      await refreshAuditLogs();
      resetServiceForm();
    } catch (error) {
      setServiceMutationError(error instanceof Error ? error.message : 'CMDB 服务保存失败');
    }
  }

  async function handleDeleteService(serviceId: string) {
    setServiceMutationError('');

    try {
      await deleteService(serviceId);
      const payload = await fetchTopology();
      setTopology(payload);
      await refreshAuditLogs();
      if (editingServiceId === serviceId) {
        resetServiceForm();
      }
    } catch (error) {
      setServiceMutationError(error instanceof Error ? error.message : 'CMDB 服务删除失败');
    }
  }

  function handleEditService(service: ServiceRecord) {
    setEditingServiceId(service.id);
    setServiceForm(service);
    setServiceMutationError('');
    setActiveView('cmdb');
  }

  async function handleRunJob(templateId: string) {
    setJobsError('');

    try {
      await runJob(templateId, currentUser?.username ?? 'console-user');
      await refreshJobs();
      await refreshAuditLogs();
    } catch (error) {
      setJobsError(error instanceof Error ? error.message : '作业执行失败');
    }
  }

  if (authLoading) {
    return (
      <div className="auth-shell auth-shell-loading">
        <div className="auth-card auth-loading-card">
          <strong>SxDevOps</strong>
          <p>正在恢复平台会话...</p>
        </div>
      </div>
    );
  }

  if (!currentUser) {
    return (
      <div className="auth-shell">
        <section className="auth-marketing">
          <div className="auth-brand-row">
            <div className="brand-mark">S</div>
            <strong>SxDevOps</strong>
          </div>
          <h1>统一运维智能体平台，让团队协同更高效</h1>
          <p>
            覆盖 CMDB、多云、可观测、发布、容器与中间件、AIOps，帮助团队在一个平台内完成日常运维协同。
          </p>
          <div className="auth-feature-grid">
            <article><strong>AIOps</strong><p>联动告警、资源与上下文，辅助定位、处置与审计。</p></article>
            <article><strong>CMDB</strong><p>统一沉淀资产、应用与关系模型，建立问题溯源底座。</p></article>
            <article><strong>可观测性</strong><p>贯通指标、日志与链路数据，帮助团队更快发现并定位异常。</p></article>
            <article><strong>任务中心</strong><p>集中编排巡检、执行与确认动作，形成闭环执行链路。</p></article>
          </div>
        </section>
        <section className="auth-panel">
          <form className="auth-form" onSubmit={handleLogin}>
            <div>
              <p className="page-kicker">进入工作台</p>
              <h2>登录</h2>
            </div>
            <label>
              用户名
              <input value={loginUsername} onChange={(event) => setLoginUsername(event.target.value)} placeholder="admin" />
            </label>
            <label>
              密码
              <input type="password" value={loginPassword} onChange={(event) => setLoginPassword(event.target.value)} placeholder="请输入密码" />
            </label>
            {authError ? <p className="error-text">{authError}</p> : null}
            <button type="submit">进入工作台</button>
            <p className="muted-text">默认账号：admin / Admin@123456</p>
          </form>
        </section>
      </div>
    );
  }

  return (
    <div className="workspace-shell">
      <aside className="sidebar">
        <div className="brand-card">
          <div className="brand-mark">S</div>
          <div>
            <strong>SxDevOps</strong>
            <p>统一运维工作台</p>
          </div>
        </div>

        <nav className="nav-groups">
          {navigationGroups.map((group) => (
            <section className="nav-group" key={group.title}>
              <p className="nav-group-title">{group.title}</p>
              {group.items.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  className={`nav-item ${activeView === item.key ? 'active' : ''}`}
                  onClick={() => setActiveView(item.key)}
                >
                  <span>{item.label}</span>
                  {!item.implemented ? <small>规划中</small> : null}
                </button>
              ))}
            </section>
          ))}
        </nav>

        <section className="sidebar-card status-card">
          <p>平台状态</p>
          <strong>{healthyCount || workspaceSummary?.health.filter((item) => item.status === 'healthy').length || 0}/{health.length || workspaceSummary?.health.length || 5}</strong>
          <span>{degradedServices.length ? `${degradedServices.length} 个组件待关注` : '核心组件运行稳定'}</span>
        </section>
      </aside>

      <div className="workspace-main">
        <header className="topbar">
          <div>
            <p className="page-kicker">AIOps 自建平台</p>
            <h1>
              {activeView === 'overview'
                ? '平台工作台'
                : activeView === 'events'
                  ? '事件墙'
                  : activeView === 'jobs'
                    ? '任务中心'
                    : activeView === 'cmdb'
                      ? 'CMDB 服务中心'
                      : activeView === 'observability'
                        ? '可观测性中心'
                        : activeView === 'host-center'
                          ? '主机中心'
                          : 'AIOps 智能助手'}
            </h1>
          </div>
          <div className="topbar-actions">
            <button type="button" className="ghost-button" onClick={() => window.location.reload()}>
              刷新工作台
            </button>
            <div className="user-pill">
              <span className="user-dot" />
              <div>
                <strong>{currentUser.display_name}</strong>
                <small>{currentUser.role}</small>
              </div>
            </div>
            <button type="button" className="ghost-button" onClick={() => void handleLogout()}>
              退出登录
            </button>
          </div>
        </header>

        {activeView === 'overview' ? (
          <main className="content-grid overview-grid">
            <section className="feature-hero card card-wide">
              <div>
                <p className="feature-kicker">统一运维智能体平台</p>
                <h2>让观测、事件、CMDB 与执行任务汇聚到一个工作台</h2>
                <p>
                  当前控制台已经串起平台健康、事件流转、作业执行、CMDB 管理、操作审计和分析入口，后续会继续向主机中心、工单系统和智能助手扩展。
                </p>
                <div className="feature-tags">
                  <span>AIOps</span>
                  <span>CMDB</span>
                  <span>任务编排</span>
                  <span>事件闭环</span>
                </div>
              </div>
              <div className="hero-metrics">
                <article>
                  <strong>{workspaceSummary?.events.open ?? events?.summary.open ?? 0}</strong>
                  <span>待处理事件</span>
                </article>
                <article>
                  <strong>{workspaceSummary?.job_total ?? jobs?.total ?? 0}</strong>
                  <span>累计作业</span>
                </article>
                <article>
                  <strong>{workspaceSummary?.cmdb.service_total ?? serviceStats.total}</strong>
                  <span>CMDB 服务</span>
                </article>
              </div>
            </section>

            <section className="card">
              <div className="section-heading">
                <h3>平台健康</h3>
                <span>{healthLoading ? '加载中' : '实时状态'}</span>
              </div>
              {healthError ? <p className="error-text">{healthError}</p> : null}
              <div className="health-stack">
                {health.map((item) => (
                  <article className={`health-row ${item.status}`} key={item.key}>
                    <div>
                      <strong>{item.name}</strong>
                      <p>{item.endpoint}</p>
                    </div>
                    <span>{item.status === 'healthy' ? '正常' : '异常'}</span>
                  </article>
                ))}
              </div>
            </section>

            <section className="card">
              <div className="section-heading">
                <h3>今日重点</h3>
                <span>工作台摘要</span>
              </div>
              <div className="kpi-grid">
                <article className="kpi-card">
                  <strong>{workspaceSummary?.events.open ?? events?.summary.open ?? 0}</strong>
                  <span>待处理告警</span>
                </article>
                <article className="kpi-card">
                  <strong>{serviceStats.highCriticality}</strong>
                  <span>高重要度服务</span>
                </article>
                <article className="kpi-card">
                  <strong>{workspaceSummary?.cmdb.edge_total ?? topology?.edges.length ?? 0}</strong>
                  <span>服务依赖边</span>
                </article>
                <article className="kpi-card accent">
                  <strong>{recentAuditLogs.length}</strong>
                  <span>最新操作记录</span>
                </article>
              </div>
            </section>

            <section className="card">
              <div className="section-heading">
                <h3>最近事件</h3>
                <button type="button" className="text-button" onClick={() => setActiveView('events')}>
                  查看全部
                </button>
              </div>
              {eventsError ? <p className="error-text">{eventsError}</p> : null}
              <div className="list-stack">
                {priorityEvents.map((item) => (
                  <article className="list-item" key={item.id}>
                    <div>
                      <strong>{item.summary}</strong>
                      <p>
                        {item.source} · {item.severity} · {formatRelativeTime(item.updated_at)}
                      </p>
                    </div>
                    <span className={`status-pill ${item.status}`}>{item.status}</span>
                  </article>
                ))}
                {!priorityEvents.length ? <p className="muted-text">暂无事件。</p> : null}
              </div>
            </section>

            <section className="card">
              <div className="section-heading">
                <h3>最近作业</h3>
                <button type="button" className="text-button" onClick={() => setActiveView('jobs')}>
                  进入任务中心
                </button>
              </div>
              {jobsError ? <p className="error-text">{jobsError}</p> : null}
              <div className="list-stack">
                {recentJobs.map((job) => (
                  <article className="list-item" key={job.id}>
                    <div>
                      <strong>{job.template_name}</strong>
                      <p>
                        {job.operator} · {formatRelativeTime(job.started_at)}
                      </p>
                    </div>
                    <span className={`status-pill ${job.status}`}>{job.status}</span>
                  </article>
                ))}
                {!recentJobs.length ? <p className="muted-text">暂无作业执行记录。</p> : null}
              </div>
            </section>

            <section className="card">
              <div className="section-heading">
                <h3>快捷动作</h3>
                <span>经由 API Gateway 聚合</span>
              </div>
              <div className="list-stack">
                {(workspaceSummary?.quick_actions ?? []).map((action) => (
                  <article className="list-item" key={action.key}>
                    <div>
                      <strong>{action.label}</strong>
                      <p>{action.template_id ?? action.filter ?? '平台动作'}</p>
                    </div>
                    <button type="button" className="ghost-button" onClick={() => setActiveView(action.key === 'cmdb' ? 'cmdb' : action.key === 'events' ? 'events' : 'jobs')}>
                      打开
                    </button>
                  </article>
                ))}
              </div>
            </section>

            <section className="card card-wide">
              <div className="section-heading">
                <h3>操作审计</h3>
                <button type="button" className="text-button" onClick={() => void refreshAuditLogs()}>
                  刷新
                </button>
              </div>
              {auditError ? <p className="error-text">{auditError}</p> : null}
              <div className="audit-table">
                {recentAuditLogs.map((item) => (
                  <article className="audit-item" key={item.id}>
                    <div>
                      <strong>{item.action}</strong>
                      <p>
                        {item.resource_type} · {item.resource_id}
                      </p>
                    </div>
                    <div>
                      <strong>{item.operator}</strong>
                      <p>{formatTimestamp(item.created_at)}</p>
                    </div>
                    <div className="audit-detail">{item.detail}</div>
                  </article>
                ))}
              </div>
            </section>
          </main>
        ) : null}

        {activeView === 'events' ? (
          <main className="content-grid">
            <section className="card card-wide">
              <div className="section-heading">
                <h3>事件墙</h3>
                <button type="button" className="ghost-button" onClick={() => void refreshEvents()}>
                  刷新事件
                </button>
              </div>
              {eventsError ? <p className="error-text">{eventsError}</p> : null}
              <div className="kpi-grid compact-kpi-grid">
                <article className="kpi-card">
                  <strong>{events?.summary.open ?? 0}</strong>
                  <span>待处理</span>
                </article>
                <article className="kpi-card">
                  <strong>{events?.summary.acknowledged ?? 0}</strong>
                  <span>已确认</span>
                </article>
                <article className="kpi-card">
                  <strong>{events?.summary.resolved ?? 0}</strong>
                  <span>已关闭</span>
                </article>
              </div>
              <form className="event-form" onSubmit={handleCreateManualEvent}>
                <input value={manualEventSource} onChange={(item) => setManualEventSource(item.target.value)} placeholder="事件来源" />
                <select value={manualEventSeverity} onChange={(item) => setManualEventSeverity(item.target.value)}>
                  <option value="critical">critical</option>
                  <option value="warning">warning</option>
                  <option value="info">info</option>
                </select>
                <input value={manualEventSummary} onChange={(item) => setManualEventSummary(item.target.value)} placeholder="事件摘要" />
                <button type="submit">新建事件</button>
              </form>
              <div className="event-table-v2">
                {(events?.events ?? []).map((item) => (
                  <article className="event-card" key={item.id}>
                    <div className="event-card-head">
                      <div>
                        <strong>{item.summary}</strong>
                        <p>
                          {item.source} · {item.severity}
                        </p>
                      </div>
                      <span className={`status-pill ${item.status}`}>{item.status}</span>
                    </div>
                    <div className="event-card-foot">
                      <span>{formatTimestamp(item.created_at)}</span>
                      <div className="inline-actions">
                        <button
                          type="button"
                          className="ghost-button"
                          onClick={() => void handleEventAction(item.id, 'ack')}
                          disabled={item.status !== 'open'}
                        >
                          确认
                        </button>
                        <button type="button" onClick={() => void handleEventAction(item.id, 'resolve')} disabled={item.status === 'resolved'}>
                          关闭
                        </button>
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            </section>
          </main>
        ) : null}

        {activeView === 'jobs' || activeView === 'host-center' ? (
          <main className="content-grid">
            <section className="card card-wide">
              <div className="section-heading">
                <h3>{activeView === 'jobs' ? '任务中心' : '主机中心 · 当前已接入任务执行能力'}</h3>
                <button type="button" className="ghost-button" onClick={() => void refreshJobs()}>
                  刷新作业
                </button>
              </div>
              {jobsError ? <p className="error-text">{jobsError}</p> : null}
              <div className="template-grid-v2">
                {jobTemplates.map((template) => (
                  <article className="template-card" key={template.id}>
                    <p className="template-category">{template.category}</p>
                    <strong>{template.name}</strong>
                    <p>{template.description}</p>
                    <button type="button" onClick={() => void handleRunJob(template.id)}>
                      执行任务
                    </button>
                  </article>
                ))}
              </div>
              <div className="job-list-v2">
                {(jobs?.jobs ?? []).map((job) => (
                  <article className="job-card" key={job.id}>
                    <div>
                      <strong>{job.template_name}</strong>
                      <p>
                        {job.operator} · {job.status} · {formatRelativeTime(job.started_at)}
                      </p>
                    </div>
                    <p>{job.result_summary || '等待执行结果'}</p>
                    <div className="job-log-inline">{job.logs.length ? job.logs.join(' | ') : '暂无日志'}</div>
                  </article>
                ))}
              </div>
            </section>
          </main>
        ) : null}

        {activeView === 'cmdb' ? (
          <main className="content-grid">
            <section className="card card-wide">
              <div className="section-heading">
                <h3>CMDB 服务中心</h3>
                <input
                  className="search-input"
                  placeholder="按服务、负责人、层级筛选"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                />
              </div>
              {topologyError ? <p className="error-text">{topologyError}</p> : null}
              {serviceMutationError ? <p className="error-text">{serviceMutationError}</p> : null}
              <div className="kpi-grid compact-kpi-grid">
                <article className="kpi-card">
                  <strong>{serviceStats.total}</strong>
                  <span>服务总数</span>
                </article>
                <article className="kpi-card">
                  <strong>{serviceStats.highCriticality}</strong>
                  <span>高优先级</span>
                </article>
                <article className="kpi-card">
                  <strong>{topology?.edges.length ?? 0}</strong>
                  <span>依赖边</span>
                </article>
              </div>
              <form className="service-form-grid" onSubmit={handleSubmitService}>
                <input
                  value={serviceForm.id}
                  onChange={(event) => setServiceForm((current) => ({ ...current, id: event.target.value }))}
                  placeholder="服务 ID"
                />
                <input
                  value={serviceForm.name}
                  onChange={(event) => setServiceForm((current) => ({ ...current, name: event.target.value }))}
                  placeholder="服务名称"
                />
                <input
                  value={serviceForm.tier}
                  onChange={(event) => setServiceForm((current) => ({ ...current, tier: event.target.value }))}
                  placeholder="层级"
                />
                <input
                  value={serviceForm.owner}
                  onChange={(event) => setServiceForm((current) => ({ ...current, owner: event.target.value }))}
                  placeholder="负责人"
                />
                <select value={serviceForm.criticality} onChange={(event) => setServiceForm((current) => ({ ...current, criticality: event.target.value }))}>
                  <option value="high">high</option>
                  <option value="medium">medium</option>
                  <option value="low">low</option>
                </select>
                <input
                  value={serviceForm.dependencies.join(',')}
                  onChange={(event) =>
                    setServiceForm((current) => ({
                      ...current,
                      dependencies: event.target.value
                        .split(',')
                        .map((value) => value.trim())
                        .filter(Boolean),
                    }))
                  }
                  placeholder="依赖服务 ID，多个用逗号分隔"
                />
                <button type="submit">{editingServiceId ? '保存修改' : '新增服务'}</button>
                <button type="button" className="ghost-button" onClick={resetServiceForm}>
                  重置
                </button>
              </form>
              <div className="service-grid-v2">
                {filteredServices.map((service) => (
                  <article className="service-card-v2" key={service.id}>
                    <div className="service-card-head">
                      <div>
                        <strong>{service.name}</strong>
                        <p>{service.id}</p>
                      </div>
                      <span className={`priority-badge ${service.criticality}`}>{service.criticality}</span>
                    </div>
                    <p>负责人: {service.owner}</p>
                    <p>层级: {service.tier}</p>
                    <p>依赖: {service.dependencies.join(', ') || '无'}</p>
                    <div className="inline-actions">
                      <button type="button" className="ghost-button" onClick={() => handleEditService(service)}>
                        编辑
                      </button>
                      <button type="button" onClick={() => void handleDeleteService(service.id)}>
                        删除
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            </section>
          </main>
        ) : null}

        {activeView === 'observability' ? (
          <main className="content-grid observability-grid">
            <section className="card">
              <div className="section-heading">
                <h3>异常检测</h3>
                <span>基于 AI Engine</span>
              </div>
              <form className="stack-form" onSubmit={handleDetectAnomaly}>
                <label>
                  时序样本
                  <textarea value={seriesInput} onChange={(event) => setSeriesInput(event.target.value)} rows={6} />
                </label>
                <label>
                  灵敏度
                  <input value={sensitivity} onChange={(event) => setSensitivity(event.target.value)} />
                </label>
                <button type="submit">执行检测</button>
              </form>
              {anomalyError ? <p className="error-text">{anomalyError}</p> : null}
              {anomalyResult ? (
                <div className="result-card">
                  <p>基线: {anomalyResult.baseline}</p>
                  <p>标准差: {anomalyResult.stddev}</p>
                  <p>异常数: {anomalyResult.anomaly_count}</p>
                  <ul>
                    {anomalyResult.anomalies.map((item) => (
                      <li key={`${item.index}-${item.value}`}>
                        点位 {item.index} = {item.value}，Z-Score {item.z_score}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </section>

            <section className="card">
              <div className="section-heading">
                <h3>根因分析</h3>
                <span>AI + CMDB</span>
              </div>
              <form className="stack-form" onSubmit={handleAnalyzeRootCause}>
                <label>
                  故障源
                  <input value={rootCauseSource} onChange={(event) => setRootCauseSource(event.target.value)} />
                </label>
                <label>
                  严重级别
                  <select value={rootCauseSeverity} onChange={(event) => setRootCauseSeverity(event.target.value)}>
                    <option value="critical">critical</option>
                    <option value="warning">warning</option>
                    <option value="info">info</option>
                  </select>
                </label>
                <label>
                  事件摘要
                  <input value={rootCauseSummary} onChange={(event) => setRootCauseSummary(event.target.value)} />
                </label>
                <label>
                  影响服务
                  <input value={impactedServices} onChange={(event) => setImpactedServices(event.target.value)} />
                </label>
                <button type="submit">执行分析</button>
              </form>
              {rootCauseError ? <p className="error-text">{rootCauseError}</p> : null}
              {rootCauseResult ? (
                <div className="result-card">
                  <p>推测根因: {rootCauseResult.probable_root_cause}</p>
                  <p>主告警: {rootCauseResult.primary_alert}</p>
                  <p>置信度: {(rootCauseResult.confidence * 100).toFixed(0)}%</p>
                  <p>影响范围: {rootCauseResult.blast_radius.join(', ')}</p>
                  <ul>
                    {rootCauseResult.reasoning.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </section>
          </main>
        ) : null}

        {activeView === 'assistant' ? (
          <main className="content-grid">
            <section className="card card-wide assistant-panel">
              <div className="assistant-header">
                <div>
                  <p className="feature-kicker">AIOps 智能助手</p>
                  <h3>把巡检、诊断建议和执行确认收敛到同一入口</h3>
                </div>
                <div className="assistant-tags">
                  <span>本地规则引擎</span>
                  <span>执行需确认</span>
                </div>
              </div>
              <div className="assistant-layout">
                <aside className="assistant-sidebar">
                  <strong>推荐问题</strong>
                  <button type="button" className="prompt-chip" onClick={() => setActiveView('jobs')}>
                    生成一份 Redis 巡检任务
                  </button>
                  <button type="button" className="prompt-chip" onClick={() => setActiveView('events')}>
                    当前未确认的严重告警有哪些
                  </button>
                  <button type="button" className="prompt-chip" onClick={() => setActiveView('cmdb')}>
                    哪些高优服务缺少依赖信息
                  </button>
                </aside>
                <div className="assistant-stage">
                  <article className="assistant-card">
                    <div className="assistant-card-head">
                      <strong>执行建议</strong>
                      <span>仅分析</span>
                    </div>
                    <p>Redis 服务状态巡检</p>
                    <ul>
                      <li>目标主机：7 台</li>
                      <li>执行方式：SSH</li>
                      <li>超时：30s</li>
                    </ul>
                    <div className="inline-actions">
                      <button type="button" onClick={() => void handleRunJob('platform-health-scan')}>
                        生成并执行
                      </button>
                      <button type="button" className="ghost-button" onClick={() => setActiveView('jobs')}>
                        转到任务中心
                      </button>
                    </div>
                  </article>

                  <article className="assistant-card muted-assistant-card">
                    <strong>执行确认原则</strong>
                    <p>后续智能助手输出的高风险动作将统一进入“执行需确认”流程，并自动写入审计日志与作业记录。</p>
                  </article>
                </div>
              </div>
            </section>
          </main>
        ) : null}
      </div>
    </div>
  );
}

export default App;
