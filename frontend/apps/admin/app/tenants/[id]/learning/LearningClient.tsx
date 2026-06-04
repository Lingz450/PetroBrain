'use client';

import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { Badge, Banner, Button, Card } from '@petrobrain/ui';

import {
  createMemory,
  getFeedbackSummary,
  listChunkWeights,
  listFeedback,
  listMemory,
  promoteFeedbackToMemory,
  updateMemory,
} from '@/lib/admin-console/api';
import type {
  ChunkWeightRow,
  FeedbackRow,
  MemoryKind,
  MemoryRow,
} from '@/lib/admin-console/types';
import { MEMORY_KINDS } from '@/lib/admin-console/types';
import { useAdminSession } from '@/lib/session/store';

import { AdminShell } from '../../../AdminShell';
import { AuthGate } from '../../../AuthGate';

/**
 * Per-tenant Learning page: one screen that surfaces the entire feedback loop.
 *
 * Sections (top to bottom):
 *   1. Summary cards - thumbs counts, active memories, weighted chunks.
 *   2. Feedback stream - latest 👍/👎 with reasons; promote-to-memory on 👎.
 *   3. Active memories - what's currently injected into the system prompt;
 *      archive button per row.
 *   4. Chunk weights - retrieval ranking nudges, sorted by weight (most-
 *      penalised first). Read-only - writes only happen via feedback so
 *      every weight change traces back to a turn.
 */
export function LearningClient({ tenantId }: { tenantId: string }) {
  const token = useAdminSession((s) => s.token);
  const principal = useAdminSession((s) => s.principal);
  const apiBaseUrl = useAdminSession((s) => s.apiBaseUrl);

  if (!token || !principal) return <AuthGate />;

  if (
    principal.role !== 'platform_admin' &&
    !(principal.role === 'admin' && principal.tenantId === tenantId)
  ) {
    return (
      <AdminShell title="Forbidden" subtitle="">
        <Banner tone="danger" title="Cross-tenant access denied">
          Use a platform_admin token to read another tenant&apos;s learning loop.
        </Banner>
      </AdminShell>
    );
  }

  return <LearningView tenantId={tenantId} token={token} apiBaseUrl={apiBaseUrl} />;
}

function LearningView({
  tenantId,
  token,
  apiBaseUrl,
}: {
  tenantId: string;
  token: string;
  apiBaseUrl: string;
}) {
  const auth = { baseUrl: apiBaseUrl, token, tenantId };

  const summary = useQuery({
    queryKey: ['learning', tenantId, 'summary'],
    queryFn: ({ signal }) => getFeedbackSummary({ ...auth, signal }),
  });
  const feedback = useQuery({
    queryKey: ['learning', tenantId, 'feedback'],
    queryFn: ({ signal }) => listFeedback({ ...auth, signal, limit: 50 }),
  });
  const memories = useQuery({
    queryKey: ['learning', tenantId, 'memories'],
    queryFn: ({ signal }) => listMemory({ ...auth, signal, status: 'active', limit: 100 }),
  });
  const weights = useQuery({
    queryKey: ['learning', tenantId, 'weights'],
    queryFn: ({ signal }) => listChunkWeights({ ...auth, signal, limit: 50 }),
  });

  return (
    <AdminShell
      title="Learning"
      subtitle="What the system has learned from your team's feedback - per tenant, never shared across tenants."
    >
      <SummaryCards
        feedbackTotal={summary.data?.total ?? 0}
        feedbackUp={summary.data?.up ?? 0}
        feedbackDown={summary.data?.down ?? 0}
        activeMemories={memories.data?.memories.length ?? 0}
        weightedChunks={weights.data?.weights.length ?? 0}
      />

      <FeedbackSection
        tenantId={tenantId}
        rows={feedback.data?.feedback ?? []}
        loading={feedback.isLoading}
        error={feedback.error}
        auth={auth}
      />

      <MemorySection
        tenantId={tenantId}
        rows={memories.data?.memories ?? []}
        loading={memories.isLoading}
        error={memories.error}
        auth={auth}
      />

      <ChunkWeightsSection
        rows={weights.data?.weights ?? []}
        loading={weights.isLoading}
        error={weights.error}
      />
    </AdminShell>
  );
}

// ---- Summary cards -----------------------------------------------------

function SummaryCards({
  feedbackTotal,
  feedbackUp,
  feedbackDown,
  activeMemories,
  weightedChunks,
}: {
  feedbackTotal: number;
  feedbackUp: number;
  feedbackDown: number;
  activeMemories: number;
  weightedChunks: number;
}) {
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
      <SummaryCard
        title="Feedback collected"
        primary={feedbackTotal.toLocaleString()}
        secondary={`👍 ${feedbackUp.toLocaleString()} · 👎 ${feedbackDown.toLocaleString()}`}
      />
      <SummaryCard
        title="Active memories"
        primary={activeMemories.toLocaleString()}
        secondary="Injected into every chat turn"
      />
      <SummaryCard
        title="Weighted chunks"
        primary={weightedChunks.toLocaleString()}
        secondary="Retrieval rank nudged by feedback"
      />
      <SummaryCard
        title="Net signal"
        primary={`${feedbackUp - feedbackDown >= 0 ? '+' : ''}${feedbackUp - feedbackDown}`}
        secondary={feedbackTotal > 0
          ? `${Math.round((feedbackUp / feedbackTotal) * 100)}% positive`
          : 'No feedback yet'}
      />
    </div>
  );
}

function SummaryCard({
  title,
  primary,
  secondary,
}: {
  title: string;
  primary: string;
  secondary: string;
}) {
  return (
    <div className="rounded-lg border border-neutral-200 bg-white p-4">
      <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-neutral-500">
        {title}
      </p>
      <p className="mt-1 text-2xl font-semibold text-neutral-800">{primary}</p>
      <p className="mt-0.5 text-xs text-neutral-500">{secondary}</p>
    </div>
  );
}

// ---- Feedback section --------------------------------------------------

function FeedbackSection({
  tenantId,
  rows,
  loading,
  error,
  auth,
}: {
  tenantId: string;
  rows: FeedbackRow[];
  loading: boolean;
  error: unknown;
  auth: { baseUrl: string; token: string; tenantId: string };
}) {
  const qc = useQueryClient();
  const [promoting, setPromoting] = useState<FeedbackRow | null>(null);
  const [promoteBody, setPromoteBody] = useState('');
  const [promoteKind, setPromoteKind] = useState<MemoryKind>('preference');
  const [promoteError, setPromoteError] = useState<string | null>(null);

  const promoteMutation = useMutation({
    mutationFn: () =>
      promoteFeedbackToMemory({
        baseUrl: auth.baseUrl,
        token: auth.token,
        tenantId: auth.tenantId,
        feedbackId: promoting!.id,
        body: promoteBody,
        kind: promoteKind,
      }),
    onSuccess: () => {
      setPromoting(null);
      setPromoteBody('');
      setPromoteKind('preference');
      setPromoteError(null);
      qc.invalidateQueries({ queryKey: ['learning', tenantId, 'memories'] });
      qc.invalidateQueries({ queryKey: ['learning', tenantId, 'summary'] });
    },
    onError: (err) => setPromoteError((err as Error).message),
  });

  function startPromote(row: FeedbackRow) {
    setPromoting(row);
    setPromoteBody(row.reason ?? '');
    setPromoteKind('preference');
    setPromoteError(null);
  }

  return (
    <Card title="Feedback stream" description="Latest 👍 / 👎 from this tenant's chat users.">
      {error ? (
        <Banner tone="danger" title="Failed to load feedback">
          {(error as Error).message}
        </Banner>
      ) : null}
      {loading ? <p className="text-sm text-neutral-500">Loading…</p> : null}
      {!loading && rows.length === 0 ? (
        <p className="text-sm text-neutral-500">
          No feedback yet. Once users start rating chat turns, ratings + reasons appear here.
        </p>
      ) : null}
      {rows.length > 0 ? (
        <div className="divide-y divide-neutral-200">
          {rows.map((row) => (
            <FeedbackRowItem key={row.id} row={row} onPromote={startPromote} />
          ))}
        </div>
      ) : null}
      {promoting ? (
        <PromoteDialog
          row={promoting}
          body={promoteBody}
          setBody={setPromoteBody}
          kind={promoteKind}
          setKind={setPromoteKind}
          error={promoteError}
          submitting={promoteMutation.isPending}
          onCancel={() => {
            setPromoting(null);
            setPromoteError(null);
          }}
          onSubmit={() => {
            if (!promoteBody.trim()) {
              setPromoteError('Memory body cannot be empty.');
              return;
            }
            promoteMutation.mutate();
          }}
        />
      ) : null}
    </Card>
  );
}

function FeedbackRowItem({
  row,
  onPromote,
}: {
  row: FeedbackRow;
  onPromote: (row: FeedbackRow) => void;
}) {
  return (
    <div className="flex items-start gap-3 py-3">
      <div className="text-lg leading-none">
        {row.rating === 'up' ? '👍' : '👎'}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2 text-xs text-neutral-500">
          <span>{new Date(row.created_utc).toLocaleString()}</span>
          <span>·</span>
          <span>user {row.user_id}</span>
          {row.module ? (
            <>
              <span>·</span>
              <Badge tone="neutral">{row.module}</Badge>
            </>
          ) : null}
        </div>
        {row.reason ? (
          <p className="mt-1 whitespace-pre-wrap text-sm text-neutral-700">{row.reason}</p>
        ) : (
          <p className="mt-1 text-sm italic text-neutral-400">No reason provided.</p>
        )}
      </div>
      {row.rating === 'down' && row.reason ? (
        <Button size="sm" variant="ghost" onClick={() => onPromote(row)}>
          Promote to memory
        </Button>
      ) : null}
    </div>
  );
}

function PromoteDialog({
  row,
  body,
  setBody,
  kind,
  setKind,
  error,
  submitting,
  onCancel,
  onSubmit,
}: {
  row: FeedbackRow;
  body: string;
  setBody: (v: string) => void;
  kind: MemoryKind;
  setKind: (k: MemoryKind) => void;
  error: string | null;
  submitting: boolean;
  onCancel: () => void;
  onSubmit: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
      <div className="w-full max-w-lg rounded-lg border border-neutral-200 bg-white p-5 shadow-lg">
        <h3 className="text-base font-semibold text-neutral-800">Promote feedback to memory</h3>
        <p className="mt-1 text-xs text-neutral-500">
          The text you write below is what will be injected into every chat turn for this tenant.
          Rewrite the user&apos;s raw reason into one safe sentence. Keep it under 280 characters.
        </p>
        <div className="mt-3 rounded-md bg-neutral-50 p-2 text-xs text-neutral-600">
          <span className="font-medium">User said:</span> {row.reason}
        </div>
        <label className="mt-3 block text-xs font-medium uppercase tracking-[0.06em] text-neutral-500">
          Memory body
        </label>
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={3}
          maxLength={280}
          placeholder="e.g. We call wellhead pressure 'WHP' on Asset-A."
          className="mt-1 w-full rounded-md border border-neutral-300 p-2 text-sm focus:border-primary-500 focus:outline-none"
        />
        <div className="mt-1 text-right text-[10px] text-neutral-400">{body.length} / 280</div>
        <label className="mt-2 block text-xs font-medium uppercase tracking-[0.06em] text-neutral-500">
          Kind
        </label>
        <select
          aria-label="Memory kind"
          value={kind}
          onChange={(e) => setKind(e.target.value as MemoryKind)}
          className="mt-1 w-full rounded-md border border-neutral-300 p-2 text-sm"
        >
          {MEMORY_KINDS.map((k) => (
            <option key={k} value={k}>
              {k}
            </option>
          ))}
        </select>
        {error ? (
          <p className="mt-2 text-xs text-danger-fg">{error}</p>
        ) : null}
        <div className="mt-4 flex items-center justify-end gap-2">
          <Button variant="ghost" onClick={onCancel} disabled={submitting}>
            Cancel
          </Button>
          <Button onClick={onSubmit} disabled={submitting}>
            {submitting ? 'Saving…' : 'Save memory'}
          </Button>
        </div>
      </div>
    </div>
  );
}

// ---- Memory section ----------------------------------------------------

function MemorySection({
  tenantId,
  rows,
  loading,
  error,
  auth,
}: {
  tenantId: string;
  rows: MemoryRow[];
  loading: boolean;
  error: unknown;
  auth: { baseUrl: string; token: string; tenantId: string };
}) {
  const qc = useQueryClient();
  const [newBody, setNewBody] = useState('');
  const [newKind, setNewKind] = useState<MemoryKind>('preference');
  const [createError, setCreateError] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: () =>
      createMemory({
        baseUrl: auth.baseUrl,
        token: auth.token,
        tenantId: auth.tenantId,
        body: newBody,
        kind: newKind,
      }),
    onSuccess: () => {
      setNewBody('');
      setNewKind('preference');
      setCreateError(null);
      qc.invalidateQueries({ queryKey: ['learning', tenantId, 'memories'] });
    },
    onError: (err) => setCreateError((err as Error).message),
  });

  const archiveMutation = useMutation({
    mutationFn: (id: string) =>
      updateMemory({
        baseUrl: auth.baseUrl,
        token: auth.token,
        tenantId: auth.tenantId,
        memoryId: id,
        status: 'archived',
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['learning', tenantId, 'memories'] }),
  });

  return (
    <Card
      title="Active memories"
      description="One-line preferences injected into every chat turn. Subordinate to base safety rules."
    >
      {error ? (
        <Banner tone="danger" title="Failed to load memories">
          {(error as Error).message}
        </Banner>
      ) : null}
      {loading ? <p className="text-sm text-neutral-500">Loading…</p> : null}
      {!loading && rows.length === 0 ? (
        <p className="text-sm text-neutral-500">
          No active memories. Promote a 👎 feedback row above, or add a manual one below.
        </p>
      ) : null}
      {rows.length > 0 ? (
        <ul className="divide-y divide-neutral-200">
          {rows.map((row) => (
            <li key={row.id} className="flex items-start gap-3 py-3">
              <Badge tone="neutral">{row.kind}</Badge>
              <div className="min-w-0 flex-1">
                <p className="text-sm text-neutral-800">{row.body}</p>
                <p className="mt-0.5 text-[11px] text-neutral-500">
                  added {new Date(row.created_utc).toLocaleDateString()} · by {row.created_by}
                  {row.source === 'promoted_feedback' ? ' · from feedback' : ''}
                </p>
              </div>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => archiveMutation.mutate(row.id)}
                disabled={archiveMutation.isPending}
              >
                Archive
              </Button>
            </li>
          ))}
        </ul>
      ) : null}
      <div className="mt-4 border-t border-neutral-200 pt-4">
        <p className="text-xs font-medium uppercase tracking-[0.06em] text-neutral-500">
          Add a new memory
        </p>
        <div className="mt-2 flex flex-wrap items-end gap-2">
          <div className="flex-1 min-w-[16rem]">
            <input
              aria-label="New memory body"
              value={newBody}
              onChange={(e) => setNewBody(e.target.value)}
              maxLength={280}
              placeholder="e.g. Default units are metric on Bono-1."
              className="h-10 w-full rounded-md border border-neutral-300 px-3 text-sm focus:border-primary-500 focus:outline-none"
            />
          </div>
          <select
            aria-label="New memory kind"
            value={newKind}
            onChange={(e) => setNewKind(e.target.value as MemoryKind)}
            className="rounded-md border border-neutral-300 px-2 py-2 text-sm"
          >
            {MEMORY_KINDS.map((k) => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
          </select>
          <Button
            onClick={() => {
              if (!newBody.trim()) {
                setCreateError('Memory body cannot be empty.');
                return;
              }
              createMutation.mutate();
            }}
            disabled={createMutation.isPending}
          >
            {createMutation.isPending ? 'Saving…' : 'Add'}
          </Button>
        </div>
        {createError ? (
          <p className="mt-2 text-xs text-danger-fg">{createError}</p>
        ) : null}
      </div>
    </Card>
  );
}

// ---- Chunk weights section --------------------------------------------

function ChunkWeightsSection({
  rows,
  loading,
  error,
}: {
  rows: ChunkWeightRow[];
  loading: boolean;
  error: unknown;
}) {
  return (
    <Card
      title="Retrieval weights"
      description="Per-tenant nudges applied after hybrid search, before rerank. Bounded [0.5, 1.5] - no amount of feedback can hide a chunk."
    >
      {error ? (
        <Banner tone="danger" title="Failed to load chunk weights">
          {(error as Error).message}
        </Banner>
      ) : null}
      {loading ? <p className="text-sm text-neutral-500">Loading…</p> : null}
      {!loading && rows.length === 0 ? (
        <p className="text-sm text-neutral-500">
          No retrieval signal yet. Once users rate chat turns that cite documents,
          the chunks involved show up here with their weight + thumbs counts.
        </p>
      ) : null}
      {rows.length > 0 ? (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-neutral-200 text-left text-xs font-medium uppercase tracking-[0.06em] text-neutral-500">
              <th className="py-2 pr-3">Chunk</th>
              <th className="py-2 pr-3">Weight</th>
              <th className="py-2 pr-3">👍</th>
              <th className="py-2 pr-3">👎</th>
              <th className="py-2">Last updated</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.chunk_id} className="border-b border-neutral-100">
                <td className="py-2 pr-3 font-mono text-xs text-neutral-700">{row.chunk_id}</td>
                <td className="py-2 pr-3">
                  <WeightBar weight={row.weight} />
                </td>
                <td className="py-2 pr-3 text-neutral-700">{row.up_count}</td>
                <td className="py-2 pr-3 text-neutral-700">{row.down_count}</td>
                <td className="py-2 text-xs text-neutral-500">
                  {new Date(row.last_updated).toLocaleString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </Card>
  );
}

function WeightBar({ weight }: { weight: number }) {
  // Range [0.5, 1.5]. Render a bar centred on 1.0 - left of centre = demoted,
  // right of centre = boosted. Pure visual; the number is the source of truth.
  const clamped = Math.max(0.5, Math.min(1.5, weight));
  const pctFromCenter = ((clamped - 1.0) / 0.5) * 50; // -50% .. +50%
  const isDown = clamped < 1.0;
  // Inline style is intentional here: the bar width is data-driven (computed
  // from the weight, which changes per row), so it can't be a static class.
  const barStyle = isDown
    ? { right: '50%', width: `${Math.abs(pctFromCenter)}%` }
    : { left: '50%', width: `${pctFromCenter}%` };
  return (
    <div
      className="flex items-center gap-2"
      title={`weight ${clamped.toFixed(2)} (${isDown ? 'demoted' : 'boosted'})`}
    >
      <div className="relative h-2 w-24 rounded-full bg-neutral-100">
        <div className="absolute left-1/2 top-0 h-2 w-px bg-neutral-300" />
        <div
          className={isDown ? 'absolute top-0 h-2 rounded-full bg-danger-fg/60' : 'absolute top-0 h-2 rounded-full bg-primary-600/70'}
          style={barStyle}
        />
      </div>
      <span className="font-mono text-xs text-neutral-700">{clamped.toFixed(2)}</span>
    </div>
  );
}
