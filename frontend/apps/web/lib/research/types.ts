import type { EvidencePack } from '@petrobrain/types';

export type ResearchDepth = 'quick' | 'standard' | 'deep';
export type ResearchStatus =
  | 'plan_ready'
  | 'approved'
  | 'rejected'
  | 'running'
  | 'completed'
  | 'failed'
  | 'stopped';

export interface ResearchPlanStep {
  id: string;
  title: string;
  question: string;
  source_types: string[];
  status: 'pending' | 'running' | 'completed' | 'skipped' | 'failed';
}

export interface ResearchSource {
  id: string;
  source_type: 'internal_document' | 'web';
  title: string;
  url?: string | null;
  snippet: string;
  document_id?: string | null;
  revision?: string | null;
  clause?: string | null;
  reliability: 'primary' | 'high' | 'medium' | 'low' | 'unknown';
  reliability_reason: string;
  freshness: 'current' | 'dated' | 'unknown';
  published_at?: string | null;
}

export interface ResearchReport {
  title: string;
  report_type: string;
  executive_summary: string;
  sections: Array<{ title: string; content: string }>;
  key_findings: string[];
  assumptions: string[];
  contradictions: string[];
  outdated_sources: string[];
  checked: string[];
  not_verified: string[];
  next_actions: string[];
  warnings: string[];
  confidence: { label: string; reason: string };
  markdown: string;
}

export interface ResearchRun {
  id: string;
  tenant_id: string;
  user_id: string;
  status: ResearchStatus;
  query: string;
  config: {
    jurisdiction?: string | null;
    asset_context?: string | null;
    project_id?: string | null;
    allowed_domains?: string[];
    internal_documents_allowed: boolean;
    web_search_allowed: boolean;
    maximum_research_steps: number;
    maximum_sources: number;
    report_type: string;
    output_depth: ResearchDepth;
    citation_required: boolean;
    safety_critical: boolean;
  };
  plan: ResearchPlanStep[];
  sources: ResearchSource[];
  report: ResearchReport | null;
  evidence_pack: EvidencePack | null;
  flags: string[];
  error?: string | null;
  created_utc: string;
  updated_utc: string;
}

export interface ResearchEvent {
  event:
    | 'started'
    | 'step_started'
    | 'source_found'
    | 'warning'
    | 'step_completed'
    | 'synthesizing'
    | 'completed'
    | 'failed'
    | 'stopped';
  data: Record<string, unknown>;
}
