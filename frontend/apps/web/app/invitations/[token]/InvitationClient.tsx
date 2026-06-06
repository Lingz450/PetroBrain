'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';

import { Logo } from '@petrobrain/ui';

import { useChatStore } from '@/lib/chat/store';
import { acceptInvitation, getInvitation } from '@/lib/onboarding/api';

interface InvitationDetails {
  company_name: string;
  email: string;
  role: string;
  department?: string | null;
  expires_at: string;
}

export function InvitationClient({ token }: { token: string }) {
  const baseUrl = useChatStore((state) => state.apiBaseUrl);
  const [details, setDetails] = useState<InvitationDetails | null>(null);
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [complete, setComplete] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    void getInvitation(baseUrl, token)
      .then((value) => { if (active) setDetails(value); })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : 'Invitation is invalid.');
      });
    return () => { active = false; };
  }, [baseUrl, token]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (password !== confirm) {
      setError('Passwords do not match.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await acceptInvitation(baseUrl, token, password);
      setComplete(true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Invitation could not be accepted.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-neutral-50 px-4 py-10 dark:bg-neutral-950">
      <section className="w-full max-w-md rounded-3xl border border-neutral-200 bg-white p-7 shadow-brand-md dark:border-neutral-800 dark:bg-neutral-900">
        <div className="text-center">
          <Logo size={48} glow />
          <p className="mt-4 text-xs font-semibold uppercase tracking-wider text-primary-600">PetroBrain invitation</p>
        </div>
        {complete ? (
          <div className="mt-7 text-center">
            <h1 className="text-2xl font-semibold">Workspace access created</h1>
            <p className="mt-2 text-sm text-neutral-500">Sign in with {details?.email} to enter the company workspace.</p>
            <Link href="/signin" className="mt-6 inline-flex rounded-xl bg-primary-600 px-5 py-2.5 text-sm font-semibold text-white">Sign in</Link>
          </div>
        ) : details ? (
          <>
            <h1 className="mt-7 text-center text-2xl font-semibold">Join {details.company_name}</h1>
            <p className="mt-2 text-center text-sm text-neutral-500">
              You were invited as {formatRole(details.role)}
              {details.department ? ` in ${details.department}` : ''}.
            </p>
            <form onSubmit={submit} className="mt-6 space-y-4">
              <p className="rounded-xl bg-neutral-50 p-3 text-sm dark:bg-neutral-950">{details.email}</p>
              <PasswordField label="Create password" value={password} onChange={setPassword} />
              <PasswordField label="Confirm password" value={confirm} onChange={setConfirm} />
              {error ? <p role="alert" className="text-sm text-red-600">{error}</p> : null}
              <button disabled={busy || password.length < 8} className="h-11 w-full rounded-xl bg-primary-600 text-sm font-semibold text-white disabled:opacity-40">
                {busy ? 'Creating access...' : 'Accept invitation'}
              </button>
            </form>
            <p className="mt-4 text-center text-xs text-neutral-500">Expires {new Date(details.expires_at).toLocaleString()}</p>
          </>
        ) : (
          <p role={error ? 'alert' : 'status'} className={`mt-7 text-center text-sm ${error ? 'text-red-600' : 'text-neutral-500'}`}>
            {error || 'Checking invitation...'}
          </p>
        )}
      </section>
    </main>
  );
}

function PasswordField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  const id = label.toLowerCase().replaceAll(' ', '-');
  return (
    <label htmlFor={id} className="block text-sm font-medium">
      {label}
      <input id={id} type="password" minLength={8} required value={value} onChange={(event) => onChange(event.target.value)} className="mt-1.5 h-11 w-full rounded-xl border px-3 dark:border-neutral-700 dark:bg-neutral-950" />
    </label>
  );
}

function formatRole(role: string) {
  return role.replaceAll('_', ' ').replace(/\b\w/g, (character) => character.toUpperCase());
}
