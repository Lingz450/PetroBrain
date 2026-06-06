'use client';

import { useRouter } from 'next/navigation';
import { useState } from 'react';

import { Logo } from '@petrobrain/ui';

import type { AccountType } from '@/lib/onboarding/api';

const OPTIONS: Array<{
  value: AccountType;
  title: string;
  description: string;
  eyebrow: string;
}> = [
  {
    value: 'individual',
    title: 'Individual',
    eyebrow: 'Personal workspace',
    description: 'For personal research, learning, technical support, and individual oil and gas work.',
  },
  {
    value: 'company',
    title: 'Company / Organization',
    eyebrow: 'Team workspace',
    description: 'For operators, service companies, regulators, consultants, and enterprise workflows.',
  },
];

export function AccountTypeClient() {
  const router = useRouter();
  const [selected, setSelected] = useState<AccountType | null>(null);

  function continueToSignup() {
    if (!selected) return;
    sessionStorage.setItem('petrobrain-signup-account-type', selected);
    router.push(`/signup?account_type=${selected}`);
  }

  return (
    <main className="relative grid min-h-screen place-items-center overflow-hidden px-4 py-10">
      <div aria-hidden className="absolute -right-40 -top-40 h-[32rem] w-[32rem] rounded-full bg-primary-200/30 blur-3xl dark:bg-primary-900/20" />
      <section className="relative w-full max-w-3xl">
        <header className="mx-auto mb-8 max-w-xl text-center">
          <Logo size={58} glow />
          <p className="mt-4 text-[11px] font-semibold uppercase tracking-[0.22em] text-primary-600 dark:text-primary-400">
            Set up PetroBrain
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">
            Are you using PetroBrain as an Individual or for a Company?
          </h1>
          <p className="mt-3 text-sm leading-6 text-neutral-500 dark:text-neutral-400">
            This determines your workspace, defaults, permissions, and onboarding path.
          </p>
        </header>

        <div className="grid gap-4 md:grid-cols-2" role="radiogroup" aria-label="Account type">
          {OPTIONS.map((option) => {
            const active = selected === option.value;
            return (
              <button
                key={option.value}
                type="button"
                role="radio"
                aria-checked={active}
                onClick={() => setSelected(option.value)}
                className={`min-h-52 rounded-2xl border p-6 text-left shadow-sm transition ${
                  active
                    ? 'border-primary-500 bg-primary-50 ring-2 ring-primary-200 dark:bg-primary-950/40 dark:ring-primary-800'
                    : 'border-neutral-200 bg-white hover:border-primary-300 dark:border-neutral-800 dark:bg-neutral-900'
                }`}
              >
                <span className="text-[11px] font-semibold uppercase tracking-wider text-primary-600 dark:text-primary-400">
                  {option.eyebrow}
                </span>
                <span className="mt-5 block text-xl font-semibold">{option.title}</span>
                <span className="mt-2 block text-sm leading-6 text-neutral-500 dark:text-neutral-400">
                  {option.description}
                </span>
                <span className={`mt-6 inline-flex h-6 w-6 items-center justify-center rounded-full border ${
                  active ? 'border-primary-600 bg-primary-600 text-white' : 'border-neutral-300'
                }`}>
                  {active ? '✓' : ''}
                </span>
              </button>
            );
          })}
        </div>

        <div className="mt-6 flex items-center justify-between">
          <button type="button" onClick={() => router.back()} className="text-sm font-medium text-neutral-500 hover:text-neutral-900 dark:hover:text-white">
            Back
          </button>
          <button
            type="button"
            disabled={!selected}
            onClick={continueToSignup}
            className="rounded-xl bg-primary-600 px-6 py-3 text-sm font-semibold text-white shadow-brand-primary disabled:cursor-not-allowed disabled:opacity-40"
          >
            Continue
          </button>
        </div>
      </section>
    </main>
  );
}
