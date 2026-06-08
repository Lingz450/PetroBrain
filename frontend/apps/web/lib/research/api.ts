import { SessionExpiredError, sessionExpiredKind } from '@/lib/chat/streamChat';

import type {
  ResearchDepth,
  ResearchEvent,
  ResearchPlanStep,
  ResearchRun,
} from './types';

interface RequestContext {
  baseUrl: string;
  token: string;
  signal?: AbortSignal;
}

export interface CreateResearchInput {
  query: string;
  jurisdiction?: string | null;
  asset_context?: string | null;
  project_id?: string | null;
  allowed_domains?: string[];
  date_from?: string | null;
  date_to?: string | null;
  internal_documents_allowed: boolean;
  web_search_allowed: boolean;
  connectors_allowed: false;
  maximum_research_steps: number;
  maximum_sources: number;
  report_type: string;
  output_depth: ResearchDepth;
  citation_required: true;
  safety_critical: boolean;
  export_format: 'markdown';
}

export class ResearchApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
  ) {
    super(detail || `Research request failed (${status})`);
    this.name = 'ResearchApiError';
  }
}

/**
 * Coerce a research record into a render-safe shape. The UI maps over
 * `plan`/`sources` directly, so a record that arrives without those arrays
 * (older rows, a partial stream payload) must never reach the components or it
 * white-screens. Guarantee the array fields here, at the boundary.
 */
export function normalizeResearchRun(raw: unknown): ResearchRun {
  const run = (raw ?? {}) as Partial<ResearchRun>;
  return {
    ...(run as ResearchRun),
    plan: Array.isArray(run.plan) ? run.plan : [],
    sources: Array.isArray(run.sources) ? run.sources : [],
    report: run.report ? normalizeReport(run.report) : null,
    evidence_pack: normalizeEvidencePack(run.evidence_pack),
  };
}

function normalizeReport(report: ResearchRun['report']): NonNullable<ResearchRun['report']> {
  if (!report) throw new Error('normalizeReport called with null');
  return {
    ...report,
    confidence: report.confidence ?? { label: 'unknown', reason: '' },
    checked: Array.isArray(report.checked) ? report.checked : [],
    not_verified: Array.isArray(report.not_verified) ? report.not_verified : [],
    contradictions: Array.isArray(report.contradictions) ? report.contradictions : [],
    warnings: Array.isArray(report.warnings) ? report.warnings : [],
    key_findings: Array.isArray(report.key_findings) ? report.key_findings : [],
    assumptions: Array.isArray(report.assumptions) ? report.assumptions : [],
    next_actions: Array.isArray(report.next_actions) ? report.next_actions : [],
    outdated_sources: Array.isArray(report.outdated_sources) ? report.outdated_sources : [],
    sections: Array.isArray(report.sections) ? report.sections : [],
  };
}

function normalizeEvidencePack(
  raw: unknown,
): ResearchRun['evidence_pack'] {
  if (!raw || typeof raw !== 'object') return null;
  const ep = raw as Record<string, unknown>;
  type EP = NonNullable<ResearchRun['evidence_pack']>;
  return {
    confidence: (ep['confidence'] as EP['confidence']) ?? { label: 'unknown', reason: '' },
    checked: Array.isArray(ep['checked']) ? (ep['checked'] as string[]) : [],
    not_verified: Array.isArray(ep['not_verified']) ? (ep['not_verified'] as string[]) : [],
    sources: Array.isArray(ep['sources']) ? (ep['sources'] as EP['sources']) : [],
    calculations: Array.isArray(ep['calculations']) ? (ep['calculations'] as EP['calculations']) : [],
    safety: (ep['safety'] as EP['safety']) ?? { requires_human_verification: false, message: '' },
    advisory: ep['advisory'] as EP['advisory'],
  };
}

export async function createResearchPlan(
  context: RequestContext,
  input: CreateResearchInput,
): Promise<ResearchRun> {
  return normalizeResearchRun(
    await json<ResearchRun>(
      await fetch(
        new URL('/research/plan', context.baseUrl),
        init(context, { method: 'POST', body: JSON.stringify(input) }),
      ),
    ),
  );
}

export async function approveResearchPlan(
  context: RequestContext,
  researchId: string,
  plan: ResearchPlanStep[],
): Promise<ResearchRun> {
  return normalizeResearchRun(
    await json<ResearchRun>(
      await fetch(
        new URL(`/research/${researchId}/approve-plan`, context.baseUrl),
        init(context, {
          method: 'POST',
          body: JSON.stringify({ action: 'approve', plan }),
        }),
      ),
    ),
  );
}

export async function listResearch(context: RequestContext): Promise<ResearchRun[]> {
  const body = await json<{ research: ResearchRun[] }>(
    await fetch(new URL('/research', context.baseUrl), init(context)),
  );
  return (body.research ?? []).map(normalizeResearchRun);
}

export async function getResearch(
  context: RequestContext,
  researchId: string,
): Promise<ResearchRun> {
  return normalizeResearchRun(
    await json<ResearchRun>(
      await fetch(
        new URL(`/research/${researchId}`, context.baseUrl),
        init(context),
      ),
    ),
  );
}

export async function stopResearch(
  context: RequestContext,
  researchId: string,
): Promise<ResearchRun> {
  return normalizeResearchRun(
    await json<ResearchRun>(
      await fetch(
        new URL(`/research/${researchId}/stop`, context.baseUrl),
        init(context, { method: 'POST' }),
      ),
    ),
  );
}

export async function streamResearch(
  context: RequestContext,
  researchId: string,
  onEvent: (event: ResearchEvent) => void,
): Promise<void> {
  const url = new URL('/research/run', context.baseUrl);
  url.searchParams.set('stream', 'true');
  const response = await fetch(
    url,
    init(context, {
      method: 'POST',
      body: JSON.stringify({ research_id: researchId }),
      headers: { Accept: 'text/event-stream' },
    }),
  );
  if (!response.ok || !response.body) throw await asError(response);
  await consumeResearchEvents(response.body, onEvent);
}

export async function exportResearch(
  context: RequestContext,
  researchId: string,
  format: 'markdown' | 'text',
): Promise<void> {
  const response = await fetch(
    new URL(`/research/${researchId}/export`, context.baseUrl),
    init(context, { method: 'POST', body: JSON.stringify({ format }) }),
  );
  if (!response.ok) throw await asError(response);
  const blob = await response.blob();
  const disposition = response.headers.get('content-disposition') ?? '';
  const filename =
    /filename="([^"]+)"/.exec(disposition)?.[1] ??
    `petrobrain-research.${format === 'markdown' ? 'md' : 'txt'}`;
  const href = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = href;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(href);
}

export async function consumeResearchEvents(
  body: ReadableStream<Uint8Array>,
  onEvent: (event: ResearchEvent) => void,
): Promise<void> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n');
    let separator = buffer.indexOf('\n\n');
    while (separator !== -1) {
      const record = buffer.slice(0, separator);
      buffer = buffer.slice(separator + 2);
      const event = parseRecord(record);
      if (event) onEvent(event);
      separator = buffer.indexOf('\n\n');
    }
  }
}

function parseRecord(record: string): ResearchEvent | null {
  let event = '';
  const data: string[] = [];
  for (const line of record.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim();
    if (line.startsWith('data:')) data.push(line.slice(5).trim());
  }
  if (!event || data.length === 0) return null;
  try {
    return { event, data: JSON.parse(data.join('\n')) } as ResearchEvent;
  } catch {
    return null;
  }
}

function init(context: RequestContext, extra: RequestInit = {}): RequestInit {
  const headers = new Headers(extra.headers);
  headers.set('Authorization', `Bearer ${context.token}`);
  if (extra.body) headers.set('Content-Type', 'application/json');
  const request: RequestInit = { ...extra, headers };
  if (context.signal) request.signal = context.signal;
  return request;
}

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) throw await asError(response);
  return (await response.json()) as T;
}

async function asError(response: Response): Promise<Error> {
  let detail = '';
  try {
    const body = (await response.clone().json()) as { detail?: unknown };
    detail =
      typeof body.detail === 'string'
        ? body.detail
        : JSON.stringify(body.detail ?? '');
  } catch {
    detail = await response.text().catch(() => '');
  }
  const sessionKind = sessionExpiredKind(response.status, detail);
  if (sessionKind) return new SessionExpiredError(sessionKind);
  return new ResearchApiError(response.status, detail);
}
