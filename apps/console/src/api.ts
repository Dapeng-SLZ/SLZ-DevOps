import type {
  AnomalyResult,
  AuditListPayload,
  EventListPayload,
  JobListPayload,
  JobRecord,
  JobTemplate,
  RootCauseResult,
  ServiceHealth,
  ServiceRecord,
  TopologyPayload,
} from './types';

const healthEndpoints = [
  { key: 'ai', name: 'AI Engine', endpoint: '/api/engine/healthz' },
  { key: 'prometheus', name: 'Prometheus', endpoint: '/api/prometheus/-/healthy' },
  { key: 'alertmanager', name: 'Alertmanager', endpoint: '/api/alertmanager/-/healthy' },
  { key: 'loki', name: 'Loki', endpoint: '/api/loki/ready' },
  { key: 'cmdb', name: 'CMDB', endpoint: '/api/cmdb/healthz' },
];

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }

  return response.json() as Promise<T>;
}

export async function fetchPlatformHealth(): Promise<ServiceHealth[]> {
  const results = await Promise.allSettled(
    healthEndpoints.map(async (item) => {
      const response = await fetch(item.endpoint);
      if (!response.ok) {
        throw new Error(`${response.status} ${response.statusText}`);
      }

      const detail = await response.text();
      return {
        key: item.key,
        name: item.name,
        endpoint: item.endpoint,
        status: 'healthy',
        detail,
      } as ServiceHealth;
    }),
  );

  return results.map((result, index) => {
    const item = healthEndpoints[index];
    if (result.status === 'fulfilled') {
      return result.value;
    }

    return {
      key: item.key,
      name: item.name,
      endpoint: item.endpoint,
      status: 'degraded',
      detail: result.reason instanceof Error ? result.reason.message : '请求失败',
    } as ServiceHealth;
  });
}

export function detectAnomaly(values: number[], sensitivity: number): Promise<AnomalyResult> {
  return fetchJson<AnomalyResult>('/api/engine/api/v1/anomaly/detect', {
    method: 'POST',
    body: JSON.stringify({ values, sensitivity }),
  });
}

export function analyzeRootCause(payload: {
  source: string;
  severity: string;
  summary: string;
  impactedServices: string[];
}): Promise<RootCauseResult> {
  return fetchJson<RootCauseResult>('/api/engine/api/v1/root-cause/analyze', {
    method: 'POST',
    body: JSON.stringify({
      alerts: [
        {
          source: payload.source,
          severity: payload.severity,
          summary: payload.summary,
        },
      ],
      impacted_services: payload.impactedServices,
    }),
  });
}

export function fetchTopology(): Promise<TopologyPayload> {
  return fetchJson<TopologyPayload>('/api/cmdb/api/v1/topology');
}

export function createService(payload: ServiceRecord): Promise<{ created: boolean }> {
  return fetchJson<{ created: boolean }>('/api/cmdb/api/v1/services', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function updateService(serviceId: string, payload: ServiceRecord): Promise<{ updated: boolean }> {
  return fetchJson<{ updated: boolean }>(`/api/cmdb/api/v1/services/${serviceId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export function deleteService(serviceId: string): Promise<{ deleted: boolean }> {
  return fetchJson<{ deleted: boolean }>(`/api/cmdb/api/v1/services/${serviceId}`, {
    method: 'DELETE',
  });
}

export function fetchJobTemplates(): Promise<{ templates: JobTemplate[] }> {
  return fetchJson<{ templates: JobTemplate[] }>('/api/jobs/api/v1/templates');
}

export function fetchJobs(): Promise<JobListPayload> {
  return fetchJson<JobListPayload>('/api/jobs/api/v1/jobs');
}

export function runJob(templateId: string, operator: string): Promise<{ accepted: boolean; job: JobRecord }> {
  return fetchJson<{ accepted: boolean; job: JobRecord }>('/api/jobs/api/v1/jobs/run', {
    method: 'POST',
    body: JSON.stringify({ template_id: templateId, operator }),
  });
}

export function fetchEvents(): Promise<EventListPayload> {
  return fetchJson<EventListPayload>('/api/engine/api/v1/events');
}

export function createManualEvent(payload: {
  source: string;
  severity: string;
  summary: string;
}): Promise<{ created: boolean }> {
  return fetchJson<{ created: boolean }>('/api/engine/api/v1/events/manual', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function acknowledgeEvent(eventId: string, operator: string): Promise<{ updated: boolean }> {
  return fetchJson<{ updated: boolean }>(`/api/engine/api/v1/events/${eventId}/ack`, {
    method: 'POST',
    body: JSON.stringify({ operator, comment: '控制台确认事件' }),
  });
}

export function resolveEvent(eventId: string, operator: string): Promise<{ updated: boolean }> {
  return fetchJson<{ updated: boolean }>(`/api/engine/api/v1/events/${eventId}/resolve`, {
    method: 'POST',
    body: JSON.stringify({ operator, comment: '控制台关闭事件' }),
  });
}

export function fetchAuditLogs(limit = 50): Promise<AuditListPayload> {
  return fetchJson<AuditListPayload>(`/api/engine/api/v1/audit?limit=${limit}`);
}