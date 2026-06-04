'use client';

import { useState } from 'react';
import clsx from 'clsx';

export interface WorkingPanelProps {
  tool: string;
  input: unknown;
  result: unknown;
  defaultOpen?: boolean;
}

export function WorkingPanel({ tool, result, defaultOpen = false }: WorkingPanelProps) {
  const [open, setOpen] = useState(defaultOpen);

  if (tool === 'web_search') {
    const count = isObject(result) && Array.isArray(result['results'])
      ? result['results'].length
      : null;
    return (
      <div className="inline-flex flex-wrap items-center gap-1.5 text-xs text-neutral-500 dark:text-neutral-400">
        <span className="rounded bg-neutral-100 px-1.5 py-0.5 text-[11px] font-medium text-neutral-700 dark:bg-neutral-800 dark:text-neutral-200">
          Checked current sources
        </span>
        {count !== null ? (
          <span className="text-neutral-400 dark:text-neutral-500">
            - {count} result{count === 1 ? '' : 's'}
          </span>
        ) : null}
      </div>
    );
  }

  return (
    <details
      open={open}
      onToggle={(e) => setOpen((e.currentTarget as HTMLDetailsElement).open)}
      className="group"
    >
      <summary className="inline-flex cursor-pointer list-none items-center gap-1.5 text-xs">
        <svg
          width="10"
          height="10"
          viewBox="0 0 20 20"
          fill="none"
          className="text-neutral-400 transition-transform [details[open]_&]:rotate-90 dark:text-neutral-500"
        >
          <path
            d="M7 5l6 5-6 5"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        <span className="rounded bg-neutral-100 px-1.5 py-0.5 text-[11px] font-medium text-neutral-700 dark:bg-neutral-800 dark:text-neutral-200">
          {userSafeToolLabel(tool)}
        </span>
      </summary>
      <div className="mt-2 space-y-3">
        <HeadlineNumbers result={result} />
        <Steps result={result} />
      </div>
    </details>
  );
}

function HeadlineNumbers({ result }: { result: unknown }) {
  if (!isObject(result)) return null;
  const entries = Object.entries(result).filter(
    ([k, v]) =>
      k !== 'banner' &&
      k !== 'working' &&
      k !== 'notes' &&
      (typeof v === 'number' || typeof v === 'string'),
  );
  if (entries.length === 0) return null;
  return (
    <dl className="grid grid-cols-2 gap-2 text-xs">
      {entries.map(([k, v]) => (
        <div key={k} className="rounded-md border border-neutral-200 bg-white p-2 dark:border-neutral-700 dark:bg-neutral-900">
          <dt className="text-[10px] font-semibold uppercase tracking-wide text-neutral-500 dark:text-neutral-400">
            {humanizeKey(k)}
          </dt>
          <dd className="font-semibold text-neutral-800 dark:text-neutral-100">{String(v)}</dd>
        </div>
      ))}
    </dl>
  );
}

function Steps({ result }: { result: unknown }) {
  if (!isObject(result)) return null;
  const working = result['working'];
  if (!Array.isArray(working) || working.length === 0) return null;
  return (
    <ol className={clsx('list-decimal space-y-1 pl-5 text-xs text-neutral-700 dark:text-neutral-300')}>
      {working.map((step, i) => (
        <li key={i}>
          {typeof step === 'string' ? step : JSON.stringify(step)}
        </li>
      ))}
    </ol>
  );
}

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v);
}

export function userSafeToolLabel(tool: string): string {
  const labels: Record<string, string> = {
    web_search: 'Checked current sources',
    build_kill_sheet: 'Built kill sheet',
    build_ptw_template: 'Built permit template',
    build_ghgemp_report: 'Built GHGEMP report',
    build_report: 'Built report',
    flaring_emissions: 'Calculated flaring emissions',
    venting_emissions: 'Calculated venting emissions',
    fugitive_tier2: 'Estimated fugitive emissions',
    fugitive_tier3: 'Estimated fugitive emissions',
    combustion_emissions: 'Calculated combustion emissions',
    reconcile_flaring: 'Reconciled flaring data',
    model_abatement: 'Modeled abatement options',
  };
  return labels[tool] ?? 'Checked supporting information';
}

function humanizeKey(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (m) => m.toUpperCase())
    .replace(/\bPpg\b/g, 'ppg')
    .replace(/\bPsi\b/g, 'psi');
}
