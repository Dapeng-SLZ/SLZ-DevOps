export type ServiceHealth = {
  key: string;
  name: string;
  endpoint: string;
  status: 'healthy' | 'degraded';
  detail: string;
};

export type AnomalyResult = {
  baseline: number;
  stddev: number;
  anomaly_count: number;
  anomalies: Array<{
    index: number;
    value: number;
    z_score: number;
  }>;
};

export type RootCauseResult = {
  probable_root_cause: string;
  primary_alert: string;
  blast_radius: string[];
  confidence: number;
  reasoning: string[];
  recommended_actions: string[];
};

export type EventRecord = {
  id: string;
  source: string;
  severity: string;
  summary: string;
  status: 'open' | 'acknowledged' | 'resolved';
  labels: Record<string, string>;
  created_at: number;
  updated_at: number;
};

export type EventListPayload = {
  total: number;
  summary: {
    open: number;
    acknowledged: number;
    resolved: number;
  };
  events: EventRecord[];
};

export type TopologyPayload = {
  services: ServiceRecord[];
  edges: Array<{
    source_id: string;
    source_name: string;
    target_id: string;
    target_name: string;
  }>;
};

export type ServiceRecord = {
  id: string;
  name: string;
  tier: string;
  owner: string;
  criticality: string;
  dependencies: string[];
};

export type JobTemplate = {
  id: string;
  name: string;
  description: string;
  category: string;
};

export type JobRecord = {
  id: string;
  template_id: string;
  template_name: string;
  operator: string;
  status: 'queued' | 'running' | 'succeeded' | 'failed';
  started_at: number;
  finished_at: number | null;
  result_summary: string;
  logs: string[];
};

export type JobListPayload = {
  total: number;
  jobs: JobRecord[];
};

export type AuditRecord = {
  id: string;
  action: string;
  resource_type: string;
  resource_id: string;
  operator: string;
  detail: string;
  created_at: number;
};

export type AuditListPayload = {
  total: number;
  items: AuditRecord[];
};