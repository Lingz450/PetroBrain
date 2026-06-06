import type { Role } from '@petrobrain/types';

const ADMIN_ROLES = new Set<Role>([
  'platform_admin',
  'admin',
  'tenant_owner',
  'company_admin',
  'compliance_admin',
]);

const TECHNICAL_ROLES = new Set<Role>([
  ...ADMIN_ROLES,
  'engineer',
  'hse',
  'hse_manager',
  'emissions_lead',
  'field_supervisor',
  'operations_user',
  'commercial_user',
  'procurement_user',
]);

export function canAdminister(role: Role | undefined): boolean {
  return Boolean(role && ADMIN_ROLES.has(role));
}

export function canAudit(role: Role | undefined): boolean {
  return canAdminister(role) || role === 'auditor';
}

export function canUseResearch(role: Role | undefined): boolean {
  return Boolean(role && TECHNICAL_ROLES.has(role));
}

export function canUseEmissions(role: Role | undefined): boolean {
  return Boolean(role && (
    ADMIN_ROLES.has(role)
    || ['engineer', 'hse', 'hse_manager', 'emissions_lead', 'operations_user'].includes(role)
  ));
}
