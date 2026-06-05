/**
 * Wire types for the in-tenant Learning page. Mirrors the FastAPI schemas
 * in routes_admin_feedback.py, routes_admin_memory.py, and
 * routes_admin_chunk_weights.py. Independent copy from the admin app's
 * lib/admin-console - the admin app isn't deployed, this lives inside
 * the chat app at /admin.
 */
export type FeedbackRating = 'up' | 'down';

export interface FeedbackRow {
  id: string;
  tenant_id: string;
  user_id: string;
  turn_id: string;
  rating: FeedbackRating;
  reason: string | null;
  module: string | null;
  metadata: Record<string, unknown>;
  created_utc: string;
}

export interface FeedbackSummary {
  tenant_id: string;
  up: number;
  down: number;
  total: number;
}

export interface FeedbackTrendPoint {
  day: string;
  up: number;
  down: number;
}

export interface FeedbackTrend {
  tenant_id: string;
  days: number;
  series: FeedbackTrendPoint[];
}

export type MemoryKind = 'terminology' | 'preference' | 'context';
export type MemoryStatus = 'active' | 'archived';
export type MemorySource = 'manual' | 'promoted_feedback';

export const MEMORY_KINDS: MemoryKind[] = ['terminology', 'preference', 'context'];

export interface MemoryRow {
  id: string;
  tenant_id: string;
  kind: MemoryKind;
  body: string;
  source: MemorySource;
  source_feedback_id: string | null;
  status: MemoryStatus;
  created_by: string;
  created_utc: string;
  updated_utc: string;
}

export interface MemoryTrendPoint {
  week_start: string;
  manual: number;
  promoted: number;
}

export interface MemoryTrend {
  tenant_id: string;
  weeks: number;
  series: MemoryTrendPoint[];
}

export interface GlossaryCandidate {
  term: string;
  count: number;
  memory_ids: string[];
}

export interface GlossaryCandidates {
  tenant_id: string;
  candidates: GlossaryCandidate[];
  min_count: number;
}

export interface ChunkWeightRow {
  tenant_id: string;
  chunk_id: number;
  weight: number;
  up_count: number;
  down_count: number;
  last_updated: string;
}

export interface ErrorEventRow {
  id: string;
  tenant_id: string;
  user_id: string;
  role: string;
  route: string;
  status: number | null;
  message: string;
  metadata: Record<string, unknown>;
  created_utc: string;
}
