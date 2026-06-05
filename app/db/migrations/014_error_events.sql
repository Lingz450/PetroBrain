-- User-visible error feed for the admin Learning page.
--
-- Frontend reports errors here when a user-facing operation fails
-- (chat stream 5xx / 4xx, feedback POST failure, share mint failure,
-- file upload failure, etc.) so admins can see issues in real time
-- without having to grep audit logs or wait for a support message.
--
-- Strictly tenant-scoped: tenant A's error feed never reaches tenant B's
-- admin view. Append-only from the app: the orchestrator does not mutate
-- or delete these rows. Retention is intentionally not enforced here -
-- the admin sees the latest N via LIMIT in the GET.

CREATE TABLE IF NOT EXISTS error_events (
    id           TEXT PRIMARY KEY,
    tenant_id    TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    user_id      TEXT NOT NULL,
    role         TEXT NOT NULL,
    route        TEXT NOT NULL,
    -- HTTP status if known (chat stream got a non-2xx), null for client-side
    -- exceptions (network drop, JSON parse fail).
    status       INTEGER,
    -- Short user-safe message - the body the user actually saw, hashed at
    -- the source if PII-sensitive (chat stream error strings are not
    -- PII; raw turn text never lands here).
    message      TEXT NOT NULL,
    -- Optional metadata bag - currently { kind, turn_id?, file?, etc }.
    metadata     JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_utc  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_error_events_tenant_created
    ON error_events (tenant_id, created_utc DESC);

CREATE INDEX IF NOT EXISTS idx_error_events_tenant_route
    ON error_events (tenant_id, route);

ALTER TABLE error_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE error_events FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_error_events ON error_events;
CREATE POLICY tenant_isolation_error_events
ON error_events
FOR ALL
USING (
    current_setting('petrobrain.tenant_id') = '*'
    OR current_setting('petrobrain.tenant_id') = tenant_id
)
WITH CHECK (
    current_setting('petrobrain.tenant_id') = '*'
    OR current_setting('petrobrain.tenant_id') = tenant_id
);
