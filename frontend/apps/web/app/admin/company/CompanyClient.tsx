'use client';

import Link from 'next/link';
import type { Route } from 'next';
import { useEffect, useMemo, useState } from 'react';

import { BackLink } from '@petrobrain/ui';

import { AuthGate } from '../../chat/components/AuthGate';
import { useChatStore } from '@/lib/chat/store';
import { getOrganization } from '@/lib/onboarding/api';

export function CompanyClient() {
  const token = useChatStore((state) => state.token);
  const principal = useChatStore((state) => state.principal);
  const baseUrl = useChatStore((state) => state.apiBaseUrl);
  const auth = useMemo(() => token ? { baseUrl, token } : null, [baseUrl, token]);
  const [company, setCompany] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!auth) return;
    void getOrganization(auth).then(setCompany).catch((reason: unknown) => {
      setError(reason instanceof Error ? reason.message : 'Could not load company profile.');
    });
  }, [auth]);

  if (!token || !principal) return <AuthGate />;

  return (
    <main className="min-h-screen bg-neutral-50 px-4 py-8 dark:bg-neutral-950">
      <div className="mx-auto max-w-5xl">
        <BackLink href="/admin" label="Admin dashboard" />
        <header className="mt-5 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-primary-600">Company workspace</p>
            <h1 className="mt-2 text-3xl font-semibold">{String(company?.company_name || 'Company settings')}</h1>
            <p className="mt-2 text-sm text-neutral-500">Profile, governance defaults, jurisdiction, assets, and team access.</p>
          </div>
          <Link href={'/admin/team' as Route} className="rounded-xl bg-primary-600 px-4 py-2.5 text-sm font-semibold text-white">Manage team</Link>
        </header>
        {error ? <p role="alert" className="mt-6 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</p> : null}
        <section className="mt-7 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <InfoCard label="Company type" value={company?.company_type} />
          <InfoCard label="Operating country" value={company?.primary_operating_country} />
          <InfoCard label="Primary jurisdiction" value={company?.primary_jurisdiction} />
          <InfoCard label="Company size" value={company?.company_size} />
          <InfoCard label="Workspace status" value={company?.onboarding_status || company?.status} />
          <InfoCard label="Tenant" value={company?.tenant_id} mono />
        </section>
        <section className="mt-7 rounded-2xl border border-neutral-200 bg-white p-6 dark:border-neutral-800 dark:bg-neutral-900">
          <h2 className="font-semibold">Enterprise defaults</h2>
          <div className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
            <p>✓ Tenant-scoped memory and company knowledge</p>
            <p>✓ Audit logging and safety escalation</p>
            <p>✓ Official-source preference and weak-source labels</p>
            <p>✓ Oil and gas workspace folders and module defaults</p>
          </div>
        </section>
      </div>
    </main>
  );
}

function InfoCard({ label, value, mono = false }: { label: string; value: unknown; mono?: boolean }) {
  return (
    <article className="rounded-2xl border border-neutral-200 bg-white p-5 dark:border-neutral-800 dark:bg-neutral-900">
      <p className="text-xs font-semibold uppercase tracking-wider text-neutral-500">{label}</p>
      <p className={`mt-2 text-sm font-medium ${mono ? 'font-mono' : ''}`}>{String(value || 'Not set')}</p>
    </article>
  );
}
