import { startTransition, useDeferredValue, useEffect, useMemo, useState } from 'react';
import {
  acknowledgeEvent,
  analyzeRootCause,
  createManualEvent,
  createService,
  deleteService,
  detectAnomaly,
  fetchAuditLogs,
  fetchJobs,
  fetchJobTemplates,
  fetchEvents,
  fetchPlatformHealth,
  fetchTopology,
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
  RootCauseResult,
  ServiceHealth,
  ServiceRecord,
  TopologyPayload,
} from './types';

const defaultSeries = '21, 22, 23, 24, 22, 25, 48, 24, 23, 22';

function App() {
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

    async function loadHealth() {
      try {
        const payload = await fetchPlatformHealth();
        if (cancelled) {
          return;
        }
        startTransition(() => {
          setHealth(payload);
          setHealthError('');
          setHealthLoading(false);
        });
      } catch (error) {
        if (cancelled) {
          return;
        }
        setHealthError(error instanceof Error ? error.message : '健康状态加载失败');
        setHealthLoading(false);
      }
    }

    async function loadTopology() {
      try {
        const payload = await fetchTopology();
        if (cancelled) {
          return;
        }
        startTransition(() => {
          setTopology(payload);
          setTopologyError('');
        });
      } catch (error) {
        if (cancelled) {
          return;
        }
        setTopologyError(error instanceof Error ? error.message : '拓扑数据加载失败');
      }
    }

    async function loadEvents() {
      try {
        const payload = await fetchEvents();
        if (cancelled) {
          return;
        }
        startTransition(() => {
          setEvents(payload);
          setEventsError('');
        });
      } catch (error) {
        if (cancelled) {
          return;
        }
        setEventsError(error instanceof Error ? error.message : '事件列表加载失败');
      }
    }

    async function loadJobs() {
      try {
        const [templatesPayload, jobsPayload] = await Promise.all([fetchJobTemplates(), fetchJobs()]);
        if (cancelled) {
          return;
        }
        startTransition(() => {
          setJobTemplates(templatesPayload.templates);
          setJobs(jobsPayload);
          setJobsError('');
        });
      } catch (error) {
        if (cancelled) {
          return;
        }
        setJobsError(error instanceof Error ? error.message : '作业中心加载失败');
      }
    }

    async function loadAudit() {
      try {
        const payload = await fetchAuditLogs();
        if (cancelled) {
          return;
        }
        startTransition(() => {
          setAuditLogs(payload);
          setAuditError('');
        });
      } catch (error) {
        if (cancelled) {
          return;
        }
        setAuditError(error instanceof Error ? error.message : '审计日志加载失败');
      }
    }

    void loadHealth();
    void loadTopology();
    void loadEvents();
    void loadJobs();
    void loadAudit();

    return () => {
      cancelled = true;
    };
  }, []);

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
        await acknowledgeEvent(eventId, 'console-user');
      } else {
        await resolveEvent(eventId, 'console-user');
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
  }

  async function handleRunJob(templateId: string) {
    setJobsError('');

    try {
      await runJob(templateId, 'console-user');
      await refreshJobs();
      await refreshAuditLogs();
    } catch (error) {
      setJobsError(error instanceof Error ? error.message : '作业执行失败');
    }
  }

  return (
    <div className="shell">
      <header className="hero">
        <div>
          <p className="eyebrow">Self-Hosted Console</p>
          <h1>SLZ 自建运维控制台</h1>
          <p className="lede">
            将 Grafana 之外的运营视图、CMDB 管理视图和 AI 分析入口独立出来，形成可单独开发、单独打包的前端平台。
          </p>
        </div>
        <div className="hero-card">
          <span>平台状态</span>
          <strong>{health.filter((item) => item.status === 'healthy').length}/{health.length || 5}</strong>
          <small>核心组件健康数</small>
        </div>
      </header>

      <main className="layout">
        <section className="panel panel-wide">
          <div className="panel-heading">
            <h2>平台总览</h2>
            <button type="button" onClick={() => window.location.reload()}>刷新</button>
          </div>
          {healthLoading ? <p className="muted">正在拉取健康状态...</p> : null}
          {healthError ? <p className="error">{healthError}</p> : null}
          <div className="health-grid">
            {health.map((item) => (
              <article key={item.key} className={`health-card ${item.status}`}>
                <div className="health-card-top">
                  <h3>{item.name}</h3>
                  <span>{item.status === 'healthy' ? '正常' : '异常'}</span>
                </div>
                <p>{item.endpoint}</p>
                <pre>{item.detail}</pre>
              </article>
            ))}
          </div>
        </section>

        <section className="panel panel-wide">
          <div className="panel-heading">
            <h2>事件中心</h2>
            <button type="button" onClick={() => void refreshEvents()}>刷新事件</button>
          </div>
          {eventsError ? <p className="error">{eventsError}</p> : null}
          <div className="event-summary-grid">
            <article className="summary-card">
              <strong>{events?.summary.open ?? 0}</strong>
              <span>待处理</span>
            </article>
            <article className="summary-card">
              <strong>{events?.summary.acknowledged ?? 0}</strong>
              <span>已确认</span>
            </article>
            <article className="summary-card">
              <strong>{events?.summary.resolved ?? 0}</strong>
              <span>已关闭</span>
            </article>
          </div>
          <form className="form-inline" onSubmit={handleCreateManualEvent}>
            <input value={manualEventSource} onChange={(item) => setManualEventSource(item.target.value)} placeholder="事件来源" />
            <select value={manualEventSeverity} onChange={(item) => setManualEventSeverity(item.target.value)}>
              <option value="critical">critical</option>
              <option value="warning">warning</option>
              <option value="info">info</option>
            </select>
            <input value={manualEventSummary} onChange={(item) => setManualEventSummary(item.target.value)} placeholder="事件摘要" />
            <button type="submit">新建人工事件</button>
          </form>
          <div className="event-table">
            {(events?.events ?? []).map((item) => (
              <article className="event-row" key={item.id}>
                <div>
                  <h3>{item.summary}</h3>
                  <p>{item.source} · {item.severity} · {item.status}</p>
                </div>
                <div className="event-actions">
                  <button type="button" onClick={() => void handleEventAction(item.id, 'ack')} disabled={item.status !== 'open'}>确认</button>
                  <button type="button" onClick={() => void handleEventAction(item.id, 'resolve')} disabled={item.status === 'resolved'}>关闭</button>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="panel panel-wide">
          <div className="panel-heading">
            <h2>作业中心</h2>
            <button type="button" onClick={() => void refreshJobs()}>刷新作业</button>
          </div>
          {jobsError ? <p className="error">{jobsError}</p> : null}
          <div className="job-template-grid">
            {jobTemplates.map((template) => (
              <article className="job-template-card" key={template.id}>
                <p className="muted">{template.category}</p>
                <h3>{template.name}</h3>
                <p>{template.description}</p>
                <button type="button" onClick={() => void handleRunJob(template.id)}>执行作业</button>
              </article>
            ))}
          </div>
          <div className="job-list">
            {(jobs?.jobs ?? []).map((job) => (
              <article className="job-row" key={job.id}>
                <div>
                  <h3>{job.template_name}</h3>
                  <p>{job.operator} · {job.status}</p>
                  <p>{job.result_summary || '等待执行结果'}</p>
                </div>
                <div className="job-logs">
                  {job.logs.length ? job.logs.join(' | ') : '暂无日志'}
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="panel panel-wide">
          <div className="panel-heading">
            <h2>操作审计</h2>
            <button type="button" onClick={() => void refreshAuditLogs()}>刷新审计</button>
          </div>
          {auditError ? <p className="error">{auditError}</p> : null}
          <div className="audit-list">
            {(auditLogs?.items ?? []).map((item) => (
              <article className="audit-row" key={item.id}>
                <div>
                  <h3>{item.action} · {item.resource_type}</h3>
                  <p>{item.operator} · {item.resource_id}</p>
                </div>
                <div className="audit-detail">{item.detail}</div>
              </article>
            ))}
          </div>
        </section>

        <section className="panel">
          <div className="panel-heading">
            <h2>异常检测</h2>
            <span>对接 AI Engine</span>
          </div>
          <form className="form-stack" onSubmit={handleDetectAnomaly}>
            <label>
              时序样本
              <textarea value={seriesInput} onChange={(event) => setSeriesInput(event.target.value)} rows={5} />
            </label>
            <label>
              灵敏度
              <input value={sensitivity} onChange={(event) => setSensitivity(event.target.value)} />
            </label>
            <button type="submit">执行检测</button>
          </form>
          {anomalyError ? <p className="error">{anomalyError}</p> : null}
          {anomalyResult ? (
            <div className="result-box">
              <p>基线: {anomalyResult.baseline}</p>
              <p>标准差: {anomalyResult.stddev}</p>
              <p>异常数: {anomalyResult.anomaly_count}</p>
              <ul>
                {anomalyResult.anomalies.map((item) => (
                  <li key={`${item.index}-${item.value}`}>点位 {item.index} = {item.value}，Z-Score {item.z_score}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </section>

        <section className="panel">
          <div className="panel-heading">
            <h2>根因分析</h2>
            <span>对接 AI + CMDB</span>
          </div>
          <form className="form-stack" onSubmit={handleAnalyzeRootCause}>
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
          {rootCauseError ? <p className="error">{rootCauseError}</p> : null}
          {rootCauseResult ? (
            <div className="result-box">
              <p>推测根因: {rootCauseResult.probable_root_cause}</p>
              <p>主告警: {rootCauseResult.primary_alert}</p>
              <p>置信度: {(rootCauseResult.confidence * 100).toFixed(0)}%</p>
              <p>影响范围: {rootCauseResult.blast_radius.join(', ')}</p>
              <ul>
                {rootCauseResult.reasoning.map((item) => <li key={item}>{item}</li>)}
              </ul>
            </div>
          ) : null}
        </section>

        <section className="panel panel-wide">
          <div className="panel-heading">
            <h2>CMDB 服务清单</h2>
            <input
              className="search"
              placeholder="按服务、负责人、层级筛选"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
          {topologyError ? <p className="error">{topologyError}</p> : null}
          {serviceMutationError ? <p className="error">{serviceMutationError}</p> : null}
          <form className="cmdb-form" onSubmit={handleSubmitService}>
            <input value={serviceForm.id} onChange={(event) => setServiceForm((current) => ({ ...current, id: event.target.value }))} placeholder="服务 ID" />
            <input value={serviceForm.name} onChange={(event) => setServiceForm((current) => ({ ...current, name: event.target.value }))} placeholder="服务名称" />
            <input value={serviceForm.tier} onChange={(event) => setServiceForm((current) => ({ ...current, tier: event.target.value }))} placeholder="层级" />
            <input value={serviceForm.owner} onChange={(event) => setServiceForm((current) => ({ ...current, owner: event.target.value }))} placeholder="负责人" />
            <select value={serviceForm.criticality} onChange={(event) => setServiceForm((current) => ({ ...current, criticality: event.target.value }))}>
              <option value="high">high</option>
              <option value="medium">medium</option>
              <option value="low">low</option>
            </select>
            <input
              value={serviceForm.dependencies.join(',')}
              onChange={(event) => setServiceForm((current) => ({
                ...current,
                dependencies: event.target.value.split(',').map((value) => value.trim()).filter(Boolean),
              }))}
              placeholder="依赖服务 ID，多个用逗号分隔"
            />
            <button type="submit">{editingServiceId ? '保存修改' : '新增服务'}</button>
            <button type="button" onClick={resetServiceForm}>重置</button>
          </form>
          <div className="service-grid">
            {filteredServices.map((service) => (
              <article className="service-card" key={service.id}>
                <div className="service-title-row">
                  <h3>{service.name}</h3>
                  <span>{service.criticality}</span>
                </div>
                <p>ID: {service.id}</p>
                <p>负责人: {service.owner}</p>
                <p>层级: {service.tier}</p>
                <p>依赖: {service.dependencies.join(', ') || '无'}</p>
                <div className="service-actions">
                  <button type="button" onClick={() => handleEditService(service)}>编辑</button>
                  <button type="button" onClick={() => void handleDeleteService(service.id)}>删除</button>
                </div>
              </article>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;