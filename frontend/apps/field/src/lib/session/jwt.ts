import type { Principal, Role } from '@petrobrain/types';

/** Decode-only JWT inspection. Server verifies on every request. */
export function decodePrincipal(token: string | null): Principal | null {
  if (!token) return null;
  const parts = token.split('.');
  if (parts.length !== 3) return null;
  try {
    const payload = JSON.parse(b64urlDecode(parts[1]!));
    if (typeof payload !== 'object' || payload === null) return null;
    const tenantId = stringClaim(payload, 'tenant_id');
    const userId = stringClaim(payload, 'user_id') ?? stringClaim(payload, 'sub');
    const role = stringClaim(payload, 'role');
    const allowed = (payload as Record<string, unknown>).allowed_assets;
    if (!tenantId || !userId || !isRole(role)) return null;
    return {
      tenantId,
      userId,
      role,
      allowedAssets: Array.isArray(allowed)
        ? allowed.filter((x): x is string => typeof x === 'string')
        : [],
    };
  } catch {
    return null;
  }
}

function stringClaim(obj: unknown, key: string): string | null {
  const value = (obj as Record<string, unknown>)[key];
  return typeof value === 'string' && value.length > 0 ? value : null;
}

function isRole(value: string | null): value is Role {
  return (
    value === 'platform_admin'
    || value === 'admin'
    || value === 'engineer'
    || value === 'field'
    || value === 'hse'
  );
}

function b64urlDecode(s: string): string {
  const padded = s.replace(/-/g, '+').replace(/_/g, '/') + '==='.slice((s.length + 3) % 4);
  if (typeof globalThis.atob === 'function') return globalThis.atob(padded);
  // Node fallback (the Hermes runtime in RN bundles atob/btoa by default,
  // but tests under Vitest in environment=node may need this branch).
  return Buffer.from(padded, 'base64').toString('binary');
}
