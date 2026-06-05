/**
 * Typed wrappers around the /admin/feedback, /admin/memory, and
 * /admin/chunk-weights endpoints. The web app at /admin uses the chat
 * user's own JWT - no tenant_id is passed; the backend defaults to the
 * principal's tenant (cross-tenant is platform_admin only, and that path
 * isn't surfaced here).
 *
 * Errors include a kind tag so the page can show typed copy:
 *   - 'session-expired'   401 with one of the get_principal detail shapes
 *   - 'forbidden'         403 (not admin)
 *   - 'network'           fetch threw / aborted
 *   - 'http'              other non-2xx
 */
import { SessionExpiredError, sessionExpiredKind } from '@/lib/chat/streamChat';

import type {
  ChunkWeightRow,
  ErrorEventRow,
  FeedbackRow,
  FeedbackSummary,
  FeedbackTrend,
  GlossaryCandidates,
  MemoryKind,
  MemoryRow,
  MemoryStatus,
  MemoryTrend,
} from './types.js';

interface ReqOpts {
  baseUrl: string;
  token: string;
  signal?: AbortSignal;
}

export class AdminLearningError extends Error {
  constructor(public readonly status: number, public readonly detail: string) {
    super(detail || `request failed (${status})`);
    this.name = 'AdminLearningError';
  }
}

async function asError(resp: Response): Promise<Error> {
  let detail = '';
  try {
    const body = (await resp.clone().json()) as { detail?: unknown };
    detail = typeof body?.detail === 'string'
      ? body.detail
      : JSON.stringify(body?.detail ?? '');
  } catch {
    detail = await resp.text().catch(() => '');
  }
  // Classify 401s the same way the chat stream does so the page can route
  // to /signin via the existing expireSession flow.
  const kind = sessionExpiredKind(resp.status, detail);
  if (kind) return new SessionExpiredError(kind);
  return new AdminLearningError(resp.status, detail);
}

async function json<T>(resp: Response): Promise<T> {
  if (!resp.ok) throw await asError(resp);
  return (await resp.json()) as T;
}

function init(opts: ReqOpts, extra: RequestInit = {}): RequestInit {
  const headers = new Headers(extra.headers);
  headers.set('Authorization', `Bearer ${opts.token}`);
  if (extra.body) headers.set('Content-Type', 'application/json');
  const out: RequestInit = { ...extra, headers };
  if (opts.signal) out.signal = opts.signal;
  return out;
}

// ---- Feedback ----------------------------------------------------------

export interface FeedbackResult {
  feedback: FeedbackRow[];
  tenant_id: string;
  limit: number;
  offset: number;
}

export async function listFeedback(
  opts: ReqOpts & { rating?: 'up' | 'down'; limit?: number; offset?: number },
): Promise<FeedbackResult> {
  const url = new URL('/admin/feedback', opts.baseUrl);
  if (opts.rating) url.searchParams.set('rating', opts.rating);
  if (opts.limit != null) url.searchParams.set('limit', String(opts.limit));
  if (opts.offset != null) url.searchParams.set('offset', String(opts.offset));
  return json<FeedbackResult>(await fetch(url, init(opts)));
}

export async function getFeedbackSummary(opts: ReqOpts): Promise<FeedbackSummary> {
  return json<FeedbackSummary>(
    await fetch(new URL('/admin/feedback/summary', opts.baseUrl), init(opts)),
  );
}

export async function getFeedbackTrend(
  opts: ReqOpts & { days?: number },
): Promise<FeedbackTrend> {
  const url = new URL('/admin/feedback/trend', opts.baseUrl);
  if (opts.days != null) url.searchParams.set('days', String(opts.days));
  return json<FeedbackTrend>(await fetch(url, init(opts)));
}

// ---- Memory ------------------------------------------------------------

export interface MemoryResult {
  memories: MemoryRow[];
  tenant_id: string;
  limit: number;
  offset: number;
}

export async function listMemory(
  opts: ReqOpts & {
    status?: MemoryStatus | null;
    kind?: MemoryKind;
    limit?: number;
    offset?: number;
  },
): Promise<MemoryResult> {
  const url = new URL('/admin/memory', opts.baseUrl);
  if (opts.status !== undefined && opts.status !== null) {
    url.searchParams.set('status', opts.status);
  }
  if (opts.kind) url.searchParams.set('kind', opts.kind);
  if (opts.limit != null) url.searchParams.set('limit', String(opts.limit));
  if (opts.offset != null) url.searchParams.set('offset', String(opts.offset));
  return json<MemoryResult>(await fetch(url, init(opts)));
}

export async function createMemory(
  opts: ReqOpts & { body: string; kind: MemoryKind },
): Promise<MemoryRow> {
  return json<MemoryRow>(
    await fetch(
      new URL('/admin/memory', opts.baseUrl),
      init(opts, {
        method: 'POST',
        body: JSON.stringify({ body: opts.body, kind: opts.kind }),
      }),
    ),
  );
}

export async function updateMemory(
  opts: ReqOpts & {
    memoryId: string;
    body?: string;
    kind?: MemoryKind;
    status?: MemoryStatus;
  },
): Promise<MemoryRow> {
  const patch: Record<string, unknown> = {};
  if (opts.body !== undefined) patch.body = opts.body;
  if (opts.kind !== undefined) patch.kind = opts.kind;
  if (opts.status !== undefined) patch.status = opts.status;
  return json<MemoryRow>(
    await fetch(
      new URL(`/admin/memory/${opts.memoryId}`, opts.baseUrl),
      init(opts, { method: 'PATCH', body: JSON.stringify(patch) }),
    ),
  );
}

export async function promoteFeedbackToMemory(
  opts: ReqOpts & { feedbackId: string; body: string; kind: MemoryKind },
): Promise<MemoryRow> {
  return json<MemoryRow>(
    await fetch(
      new URL(`/admin/memory/from-feedback/${opts.feedbackId}`, opts.baseUrl),
      init(opts, {
        method: 'POST',
        body: JSON.stringify({ body: opts.body, kind: opts.kind }),
      }),
    ),
  );
}

export async function getMemoryTrend(
  opts: ReqOpts & { weeks?: number },
): Promise<MemoryTrend> {
  const url = new URL('/admin/memory/trend', opts.baseUrl);
  if (opts.weeks != null) url.searchParams.set('weeks', String(opts.weeks));
  return json<MemoryTrend>(await fetch(url, init(opts)));
}

export async function getGlossaryCandidates(
  opts: ReqOpts & { minCount?: number },
): Promise<GlossaryCandidates> {
  const url = new URL('/admin/memory/glossary-candidates', opts.baseUrl);
  if (opts.minCount != null) url.searchParams.set('min_count', String(opts.minCount));
  return json<GlossaryCandidates>(await fetch(url, init(opts)));
}

// ---- Chunk weights -----------------------------------------------------

export interface ChunkWeightsResult {
  weights: ChunkWeightRow[];
  tenant_id: string;
  limit: number;
  offset: number;
}

export async function listChunkWeights(
  opts: ReqOpts & { limit?: number; offset?: number },
): Promise<ChunkWeightsResult> {
  const url = new URL('/admin/chunk-weights', opts.baseUrl);
  if (opts.limit != null) url.searchParams.set('limit', String(opts.limit));
  if (opts.offset != null) url.searchParams.set('offset', String(opts.offset));
  return json<ChunkWeightsResult>(await fetch(url, init(opts)));
}

// ---- User-visible errors ----------------------------------------------

export interface ErrorEventsResult {
  errors: ErrorEventRow[];
  tenant_id: string;
  limit: number;
  offset: number;
}

export async function listErrors(
  opts: ReqOpts & { limit?: number; offset?: number },
): Promise<ErrorEventsResult> {
  const url = new URL('/admin/errors', opts.baseUrl);
  if (opts.limit != null) url.searchParams.set('limit', String(opts.limit));
  if (opts.offset != null) url.searchParams.set('offset', String(opts.offset));
  return json<ErrorEventsResult>(await fetch(url, init(opts)));
}
