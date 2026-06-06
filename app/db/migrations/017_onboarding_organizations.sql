CREATE TABLE IF NOT EXISTS onboarding_profiles (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    tenant_id       TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    account_type    TEXT NOT NULL CHECK (account_type IN ('individual', 'company')),
    status          TEXT NOT NULL DEFAULT 'in_progress'
                    CHECK (status IN ('not_started', 'in_progress', 'completed', 'skipped')),
    current_step    TEXT NOT NULL DEFAULT 'account_type',
    answers         JSONB NOT NULL DEFAULT '{}'::jsonb,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, user_id)
);

CREATE TABLE IF NOT EXISTS organization_invitations (
    invitation_id       TEXT PRIMARY KEY,
    tenant_id           TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    email               TEXT NOT NULL,
    role                TEXT NOT NULL,
    department          TEXT,
    message             TEXT,
    invite_token_hash   TEXT NOT NULL UNIQUE,
    status              TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'accepted', 'expired', 'revoked')),
    invited_by_user_id  TEXT NOT NULL,
    expires_at          TIMESTAMPTZ NOT NULL,
    accepted_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_onboarding_profiles_tenant
    ON onboarding_profiles (tenant_id, user_id);
CREATE INDEX IF NOT EXISTS idx_org_invites_tenant
    ON organization_invitations (tenant_id, status);

ALTER TABLE onboarding_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE onboarding_profiles FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS onboarding_profiles_tenant_isolation ON onboarding_profiles;
CREATE POLICY onboarding_profiles_tenant_isolation ON onboarding_profiles
USING (
    current_setting('petrobrain.tenant_id') = '*'
    OR current_setting('petrobrain.tenant_id') = tenant_id
)
WITH CHECK (
    current_setting('petrobrain.tenant_id') = '*'
    OR current_setting('petrobrain.tenant_id') = tenant_id
);

ALTER TABLE organization_invitations ENABLE ROW LEVEL SECURITY;
ALTER TABLE organization_invitations FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS organization_invitations_tenant_isolation
    ON organization_invitations;
CREATE POLICY organization_invitations_tenant_isolation
ON organization_invitations
USING (
    current_setting('petrobrain.tenant_id') = '*'
    OR current_setting('petrobrain.tenant_id') = tenant_id
)
WITH CHECK (
    current_setting('petrobrain.tenant_id') = '*'
    OR current_setting('petrobrain.tenant_id') = tenant_id
);

ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;
ALTER TABLE users ADD CONSTRAINT users_role_check CHECK (
    role IN (
        'platform_admin', 'admin', 'tenant_owner', 'company_admin',
        'compliance_admin', 'hse_manager', 'emissions_lead', 'engineer',
        'field', 'field_supervisor', 'operations_user', 'commercial_user',
        'procurement_user', 'auditor', 'viewer', 'hse'
    )
);
