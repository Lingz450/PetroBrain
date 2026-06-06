import type { Role } from '@petrobrain/types';

export type AccountType = 'individual' | 'company';

export interface OnboardingStatus {
  account_type: AccountType | null;
  onboarding_status: 'not_started' | 'in_progress' | 'completed' | 'skipped';
  current_step: string;
  answers: Record<string, unknown>;
  tenant_id: string;
  workspace_name: string;
}

export interface OnboardingOptions {
  account_types: AccountType[];
  focus_areas: string[];
  use_cases: string[];
  regions: string[];
  company_types: string[];
  company_sizes: string[];
  regulator_focus: string[];
  asset_types: string[];
  roles: Role[];
}

export interface Invitation {
  invitation_id: string;
  tenant_id: string;
  email: string;
  role: Role;
  department?: string | null;
  status: 'pending' | 'accepted' | 'expired' | 'revoked';
  invited_by_user_id: string;
  expires_at: string;
  created_at: string;
  invite_path?: string;
  delivery?: { email_sent: boolean; message: string };
}

interface Auth {
  baseUrl: string;
  token: string;
}

async function request<T>(auth: Auth, path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${auth.baseUrl}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${auth.token}`,
      ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({})) as { detail?: string };
    throw new Error(payload.detail || `Request failed (${response.status})`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export function getOnboardingStatus(auth: Auth) {
  return request<OnboardingStatus>(auth, '/onboarding/status');
}

export function getOnboardingOptions(auth: Auth) {
  return request<OnboardingOptions>(auth, '/onboarding/options');
}

export function selectAccountType(auth: Auth, accountType: AccountType) {
  return request(auth, '/onboarding/account-type', {
    method: 'POST',
    body: JSON.stringify({ account_type: accountType }),
  });
}

export function saveIndividual(auth: Auth, payload: Record<string, unknown>) {
  return request(auth, '/onboarding/individual', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function saveCompany(auth: Auth, payload: Record<string, unknown>) {
  return request(auth, '/onboarding/company', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function addOnboardingAsset(auth: Auth, payload: Record<string, unknown>) {
  return request(auth, '/onboarding/company/assets', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function completeOnboarding(auth: Auth, skippedOptional = false) {
  return request<{ recommended_destination: string }>(auth, '/onboarding/complete', {
    method: 'POST',
    body: JSON.stringify({ skipped_optional: skippedOptional }),
  });
}

export function getOrganization(auth: Auth) {
  return request<Record<string, unknown>>(auth, '/organizations/current');
}

export function listMembers(auth: Auth) {
  return request<{ members: Array<Record<string, unknown>> }>(
    auth,
    '/organizations/current/members',
  );
}

export function listInvitations(auth: Auth) {
  return request<{ invitations: Invitation[] }>(
    auth,
    '/organizations/current/invitations',
  );
}

export function createInvitation(
  auth: Auth,
  payload: { email: string; role: Role; department?: string; message?: string },
) {
  return request<Invitation>(auth, '/organizations/current/invitations', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function updateInvitation(
  auth: Auth,
  invitationId: string,
  payload: { action: 'update' | 'resend' | 'revoke'; role?: Role; department?: string },
) {
  return request<Invitation>(
    auth,
    `/organizations/current/invitations/${invitationId}`,
    { method: 'PATCH', body: JSON.stringify(payload) },
  );
}

export function updateMember(auth: Auth, memberId: string, role: Role) {
  return request(auth, `/admin/company/members/${memberId}`, {
    method: 'PATCH',
    body: JSON.stringify({ role }),
  });
}

export function removeMember(auth: Auth, memberId: string) {
  return request<void>(auth, `/admin/company/members/${memberId}`, {
    method: 'DELETE',
  });
}

export async function getInvitation(baseUrl: string, token: string) {
  const response = await fetch(`${baseUrl}/invitations/${encodeURIComponent(token)}`);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({})) as { detail?: string };
    throw new Error(payload.detail || 'Invitation is invalid or expired.');
  }
  return response.json() as Promise<{
    company_name: string;
    email: string;
    role: Role;
    department?: string | null;
    expires_at: string;
  }>;
}

export async function acceptInvitation(baseUrl: string, token: string, password: string) {
  const response = await fetch(`${baseUrl}/invitations/accept`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token, password }),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({})) as { detail?: string };
    throw new Error(payload.detail || 'Invitation could not be accepted.');
  }
  return response.json() as Promise<{ status: string; tenant_id: string; user_id: string }>;
}
