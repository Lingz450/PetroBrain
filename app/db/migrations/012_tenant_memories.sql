-- Tenant-scoped prompt memory (slice 2 of the learning loop).
--
-- Each row is one short sentence injected into the system prompt for every
-- chat turn in that tenant. Memories come from two places:
--   1. Admin creates them by hand ("we call wellhead pressure 'WHP'").
--   2. Admin promotes a 👎 reason into a memory ("the model called this
--      asset by its alias; correct name is Bono-1").
--
-- Hard ceilings enforced in app code (and documented here) keep the prompt
-- finite:
--   * status='active' rows only: ~20 max per tenant.
--   * body length: <= 280 chars (one sentence).
--   * combined active body: <= ~2000 chars per tenant.
--
-- Safety:
--   * RLS isolates strictly per-tenant. A memory in tenant A never reaches
--     tenant B's prompt.
--   * The orchestrator's prompt assembly REFUSES to inject memories whose
--     body looks like a prompt-injection attempt (override-instruction
--     verbs, safety-bypass phrases, fake role markers). The same check
--     runs at write time in the admin route, so a hostile admin can't
--     persist a memory the orchestrator would refuse.
--   * Memories are advisory context; they CANNOT override the base
--     system prompt's safety rules, the deterministic calc engine, or the
--     guardrail layer. The base prompt is appended first; module preambles
--     second; memory last but explicitly subordinate.
--
-- Append-then-archive shape: rows are never hard-deleted. status='archived'
-- removes them from the prompt but keeps the audit trail.

CREATE TABLE IF NOT EXISTS tenant_memories (
    id               TEXT PRIMARY KEY,
    tenant_id        TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    kind             TEXT NOT NULL DEFAULT 'preference'
                     CHECK (kind IN ('terminology', 'preference', 'context')),
    body             TEXT NOT NULL,
    source           TEXT NOT NULL DEFAULT 'manual'
                     CHECK (source IN ('manual', 'promoted_feedback')),
    source_feedback_id TEXT,
    status           TEXT NOT NULL DEFAULT 'active'
                     CHECK (status IN ('active', 'archived')),
    created_by       TEXT NOT NULL,
    created_utc      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_utc      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tenant_memories_tenant_status
    ON tenant_memories (tenant_id, status);

CREATE INDEX IF NOT EXISTS idx_tenant_memories_tenant_kind
    ON tenant_memories (tenant_id, kind);

ALTER TABLE tenant_memories ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_memories FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_memories ON tenant_memories;
CREATE POLICY tenant_isolation_memories
ON tenant_memories
FOR ALL
USING (
    current_setting('petrobrain.tenant_id') = '*'
    OR current_setting('petrobrain.tenant_id') = tenant_id
)
WITH CHECK (
    current_setting('petrobrain.tenant_id') = '*'
    OR current_setting('petrobrain.tenant_id') = tenant_id
);
