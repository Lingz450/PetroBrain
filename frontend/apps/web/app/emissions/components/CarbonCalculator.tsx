'use client';

import { useMemo, useState } from 'react';

import { Card } from '@petrobrain/ui';

interface SummaryRow {
  id: string;
  source: string;
  unit: string;
  factor: number;
  activity: string;
}

interface BreakdownRow {
  id: string;
  month: string;
  amount: string;
  unitPrice: string;
  activity: string;
}

const DEFAULT_SUMMARY_ROWS: SummaryRow[] = [
  { id: 'diesel-generator', source: 'Diesel generator fuel', unit: 'Litres', factor: 2.68, activity: '' },
  { id: 'company-vehicles', source: 'Company vehicles fuel', unit: 'Litres', factor: 2.31, activity: '' },
  { id: 'grid-electricity', source: 'Grid electricity', unit: 'kWh', factor: 0.5, activity: '' },
  { id: 'natural-gas', source: 'Natural gas', unit: 'm3', factor: 2, activity: '' },
];

const DEFAULT_MONTHS: BreakdownRow[] = [
  { id: 'jan', month: 'January', amount: '', unitPrice: '', activity: '' },
  { id: 'feb', month: 'February', amount: '', unitPrice: '', activity: '' },
  { id: 'mar', month: 'March', amount: '', unitPrice: '', activity: '' },
  { id: 'apr', month: 'April', amount: '', unitPrice: '', activity: '' },
];

const BREAKDOWNS = [
  {
    id: 'company-vehicles',
    title: 'Company vehicle fuel',
    source: 'Company vehicles fuel',
    description: 'Enter monthly spend and pump price; litres and CO2 emissions calculate automatically.',
    unit: 'Litres',
    factor: 2.31,
    mode: 'spend',
    defaultRows: [
      { id: 'jan', month: 'January', amount: '167742.70', unitPrice: '1325', activity: '' },
      { id: 'feb', month: 'February', amount: '194134.00', unitPrice: '1325', activity: '' },
      { id: 'mar', month: 'March', amount: '251951.00', unitPrice: '1325', activity: '' },
      { id: 'apr', month: 'April', amount: '394899.00', unitPrice: '1325', activity: '' },
    ],
  },
  {
    id: 'diesel-generator',
    title: 'Diesel generator fuel',
    source: 'Diesel generator fuel',
    description: 'Track generator diesel consumption by month or derive litres from fuel spend.',
    unit: 'Litres',
    factor: 2.68,
    mode: 'spend',
    defaultRows: DEFAULT_MONTHS,
  },
  {
    id: 'grid-electricity',
    title: 'Grid electricity',
    source: 'Grid electricity',
    description: 'Enter metered monthly electricity consumption from utility bills.',
    unit: 'kWh',
    factor: 0.5,
    mode: 'activity',
    defaultRows: DEFAULT_MONTHS,
  },
  {
    id: 'natural-gas',
    title: 'Natural gas',
    source: 'Natural gas',
    description: 'Enter monthly natural gas use from plant meters or supplier statements.',
    unit: 'm3',
    factor: 2,
    mode: 'activity',
    defaultRows: DEFAULT_MONTHS,
  },
] as const;

type BreakdownId = (typeof BREAKDOWNS)[number]['id'];
type BreakdownConfig = (typeof BREAKDOWNS)[number];

interface BreakdownTotals {
  amount: number;
  activity: number;
  emissions: number;
}

export function CarbonCalculator() {
  const [summaryRows, setSummaryRows] = useState(DEFAULT_SUMMARY_ROWS);
  const [breakdownRows, setBreakdownRows] = useState<Record<BreakdownId, BreakdownRow[]>>(() => {
    return Object.fromEntries(BREAKDOWNS.map((item) => [item.id, item.defaultRows])) as Record<
      BreakdownId,
      BreakdownRow[]
    >;
  });

  const summaryTotal = useMemo(
    () => summaryRows.reduce((sum, row) => sum + activity(row.activity) * row.factor, 0),
    [summaryRows],
  );

  function updateSummary(id: string, activityValue: string) {
    setSummaryRows((rows) =>
      rows.map((row) => (row.id === id ? { ...row, activity: activityValue } : row)),
    );
  }

  function updateBreakdown(breakdownId: BreakdownId, rowId: string, patch: Partial<BreakdownRow>) {
    setBreakdownRows((current) => ({
      ...current,
      [breakdownId]: current[breakdownId].map((row) => (row.id === rowId ? { ...row, ...patch } : row)),
    }));
  }

  const breakdownTotals = useMemo(() => {
    return Object.fromEntries(
      BREAKDOWNS.map((item) => [item.id, calculateBreakdown(item, breakdownRows[item.id])]),
    ) as Record<BreakdownId, BreakdownTotals>;
  }, [breakdownRows]);

  const operatingTotal = Object.values(breakdownTotals).reduce((sum, total) => sum + total.emissions, 0);

  function syncSummaryFromBreakdowns() {
    setSummaryRows((rows) =>
      rows.map((row) => ({
        ...row,
        activity: formatInput(breakdownTotals[row.id as BreakdownId]?.activity ?? activity(row.activity)),
      })),
    );
  }

  return (
    <Card title="Carbon calculator" description="Quick CO2 worksheet for fuel, electricity, gas, vehicles, and power usage.">
      <div className="space-y-5">
        <section aria-label="CO2 summary" className="space-y-2">
          <div className="flex flex-wrap items-end justify-between gap-2">
            <div>
              <h2 className="text-sm font-semibold text-neutral-800 dark:text-neutral-100">CO2 - Carbon dioxide</h2>
              <p className="text-xs text-neutral-500 dark:text-neutral-400">
                Enter activity data; totals calculate in kilograms of CO2.
              </p>
            </div>
            <SummaryPill label="Total emissions" value={`${formatNumber(summaryTotal)} kgCO2`} />
          </div>

          <div className="overflow-x-auto rounded-md border border-neutral-300 shadow-[inset_0_0_0_1px_rgba(212,212,212,0.7)] dark:border-neutral-700 dark:shadow-[inset_0_0_0_1px_rgba(64,64,64,0.8)]">
            <table className="min-w-full border-collapse text-sm">
              <thead className="bg-neutral-100 text-xs uppercase tracking-wide text-neutral-600 dark:bg-neutral-800/80 dark:text-neutral-300">
                <tr>
                  <th scope="col" className="border border-neutral-300 px-3 py-2 text-left dark:border-neutral-700">Source</th>
                  <th scope="col" className="border border-neutral-300 px-3 py-2 text-left dark:border-neutral-700">Activity data</th>
                  <th scope="col" className="border border-neutral-300 px-3 py-2 text-left dark:border-neutral-700">Unit</th>
                  <th scope="col" className="border border-neutral-300 px-3 py-2 text-right dark:border-neutral-700">Emission factor</th>
                  <th scope="col" className="border border-neutral-300 px-3 py-2 text-right dark:border-neutral-700">Total emissions</th>
                </tr>
              </thead>
              <tbody className="bg-white dark:bg-neutral-900/60">
                {summaryRows.map((row) => {
                  const total = activity(row.activity) * row.factor;
                  return (
                    <tr key={row.id}>
                      <td className="border border-neutral-300 px-3 py-2 font-medium text-neutral-800 dark:border-neutral-700 dark:text-neutral-100">{row.source}</td>
                      <td className="min-w-40 border border-neutral-300 px-3 py-2 dark:border-neutral-700">
                        <input
                          aria-label={`${row.source} activity data`}
                          type="number"
                          min="0"
                          step="any"
                          value={row.activity}
                          onChange={(e) => updateSummary(row.id, e.target.value)}
                          className={inputClassName}
                        />
                      </td>
                      <td className="border border-neutral-300 px-3 py-2 text-neutral-600 dark:border-neutral-700 dark:text-neutral-300">{row.unit}</td>
                      <td className="border border-neutral-300 px-3 py-2 text-right tabular-nums text-neutral-800 dark:border-neutral-700 dark:text-neutral-200">
                        {formatNumber(row.factor)}
                      </td>
                      <td className="border border-neutral-300 px-3 py-2 text-right font-semibold tabular-nums text-neutral-900 dark:border-neutral-700 dark:text-neutral-100">
                        {formatNumber(total)}
                      </td>
                    </tr>
                  );
                })}
                <tr className="bg-neutral-100 font-semibold dark:bg-neutral-800/80">
                  <td className="border border-neutral-300 px-3 py-2 text-neutral-900 dark:border-neutral-700 dark:text-neutral-100">Total emissions</td>
                  <td className="border border-neutral-300 px-3 py-2 dark:border-neutral-700" colSpan={3} />
                  <td className="border border-neutral-300 px-3 py-2 text-right tabular-nums text-neutral-900 dark:border-neutral-700 dark:text-neutral-100">
                    {formatNumber(summaryTotal)}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section aria-label="Monthly operating breakdowns" className="space-y-3">
          <div className="flex flex-wrap items-end justify-between gap-2">
            <div>
              <h2 className="text-sm font-semibold uppercase tracking-wide text-neutral-700 dark:text-neutral-200">
                Monthly operating breakdowns
              </h2>
              <p className="text-xs text-neutral-500 dark:text-neutral-400">
                Calculate detailed monthly emissions for transport, generators, grid power, and gas use.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={syncSummaryFromBreakdowns}
                className="h-9 rounded-lg border border-neutral-200 bg-white px-3 text-xs font-semibold text-neutral-700 transition-colors hover:border-primary-300 hover:bg-primary-50 hover:text-primary-700 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-200 dark:hover:border-primary-600 dark:hover:bg-primary-900/30"
              >
                Use breakdown totals
              </button>
              <SummaryPill label="Operating emissions" value={`${formatNumber(operatingTotal)} kgCO2`} />
            </div>
          </div>

          <div className="space-y-4">
            {BREAKDOWNS.map((item) => (
              <BreakdownTable
                key={item.id}
                config={item}
                rows={breakdownRows[item.id]}
                totals={breakdownTotals[item.id]}
                onChange={(rowId, patch) => updateBreakdown(item.id, rowId, patch)}
              />
            ))}
          </div>
        </section>

        <section aria-label="Reduction strategies" className="grid grid-cols-1 gap-3 md:grid-cols-3">
          {[
            ['Hybrid work days', 'Reduce commute and pool vehicle fuel demand.'],
            ['Electric vehicles as pool vehicles', 'Switching to EV or plug-in hybrid vehicles can reduce vehicle emissions.'],
            ['Solar panel as alternative energy', 'Offset grid electricity and diesel generator runtime.'],
          ].map(([title, body]) => (
            <div key={title} className="rounded-xl border border-neutral-200 bg-neutral-50 p-3 dark:border-neutral-700 dark:bg-neutral-900/60">
              <p className="text-sm font-semibold text-neutral-800 dark:text-neutral-100">{title}</p>
              <p className="mt-1 text-xs leading-relaxed text-neutral-500 dark:text-neutral-400">{body}</p>
            </div>
          ))}
        </section>
      </div>
    </Card>
  );
}

function BreakdownTable({
  config,
  rows,
  totals,
  onChange,
}: {
  config: BreakdownConfig;
  rows: BreakdownRow[];
  totals: BreakdownTotals;
  onChange: (rowId: string, patch: Partial<BreakdownRow>) => void;
}) {
  const isSpendMode = config.mode === 'spend';
  return (
    <article className="space-y-2">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-neutral-800 dark:text-neutral-100">{config.title}</h3>
          <p className="text-xs text-neutral-500 dark:text-neutral-400">{config.description}</p>
        </div>
        <SummaryPill label={`${config.title} total`} value={`${formatNumber(totals.emissions)} kgCO2`} />
      </div>

      <div className="overflow-x-auto rounded-md border border-neutral-300 shadow-[inset_0_0_0_1px_rgba(212,212,212,0.7)] dark:border-neutral-700 dark:shadow-[inset_0_0_0_1px_rgba(64,64,64,0.8)]">
        <table className="min-w-full border-collapse text-sm">
          <thead className="bg-neutral-100 text-xs uppercase tracking-wide text-neutral-600 dark:bg-neutral-800/80 dark:text-neutral-300">
            <tr>
              <th scope="col" className="border border-neutral-300 px-3 py-2 text-left dark:border-neutral-700">Source</th>
              <th scope="col" className="border border-neutral-300 px-3 py-2 text-left dark:border-neutral-700">Month</th>
              {isSpendMode ? (
                <>
                  <th scope="col" className="border border-neutral-300 px-3 py-2 text-right dark:border-neutral-700">Amount</th>
                  <th scope="col" className="border border-neutral-300 px-3 py-2 text-right dark:border-neutral-700">Unit price</th>
                </>
              ) : (
                <th scope="col" className="border border-neutral-300 px-3 py-2 text-right dark:border-neutral-700">Activity data</th>
              )}
              <th scope="col" className="border border-neutral-300 px-3 py-2 text-right dark:border-neutral-700">Total {config.unit.toLowerCase()}</th>
              <th scope="col" className="border border-neutral-300 px-3 py-2 text-right dark:border-neutral-700">Emission factor</th>
              <th scope="col" className="border border-neutral-300 px-3 py-2 text-right dark:border-neutral-700">CO2 emissions</th>
            </tr>
          </thead>
          <tbody className="bg-white dark:bg-neutral-900/60">
            {rows.map((row, index) => {
              const activityValue = rowActivity(config, row);
              const emissions = activityValue * config.factor;
              return (
                <tr key={row.id}>
                  <td className="border border-neutral-300 px-3 py-2 font-medium text-neutral-800 dark:border-neutral-700 dark:text-neutral-100">
                    {index === 0 ? config.source : ''}
                  </td>
                  <td className="border border-neutral-300 px-3 py-2 text-neutral-700 dark:border-neutral-700 dark:text-neutral-300">{row.month}</td>
                  {isSpendMode ? (
                    <>
                      <td className="min-w-36 border border-neutral-300 px-3 py-2 dark:border-neutral-700">
                        <NumberCell
                          label={`${config.title} ${row.month} amount`}
                          value={row.amount}
                          min="0"
                          onChange={(value) => onChange(row.id, { amount: value })}
                        />
                      </td>
                      <td className="min-w-32 border border-neutral-300 px-3 py-2 dark:border-neutral-700">
                        <NumberCell
                          label={`${config.title} ${row.month} unit price`}
                          value={row.unitPrice}
                          min="1"
                          onChange={(value) => onChange(row.id, { unitPrice: value })}
                        />
                      </td>
                    </>
                  ) : (
                    <td className="min-w-36 border border-neutral-300 px-3 py-2 dark:border-neutral-700">
                      <NumberCell
                        label={`${config.title} ${row.month} activity data`}
                        value={row.activity}
                        min="0"
                        onChange={(value) => onChange(row.id, { activity: value })}
                      />
                    </td>
                  )}
                  <td className="border border-neutral-300 px-3 py-2 text-right tabular-nums text-neutral-800 dark:border-neutral-700 dark:text-neutral-200">
                    {formatNumber(activityValue)}
                  </td>
                  <td className="border border-neutral-300 px-3 py-2 text-right tabular-nums text-neutral-800 dark:border-neutral-700 dark:text-neutral-200">
                    {formatNumber(config.factor)}
                  </td>
                  <td className="border border-neutral-300 px-3 py-2 text-right font-semibold tabular-nums text-neutral-900 dark:border-neutral-700 dark:text-neutral-100">
                    {formatNumber(emissions)}
                  </td>
                </tr>
              );
            })}
            <tr className="bg-neutral-100 font-semibold dark:bg-neutral-800/80">
              <td className="border border-neutral-300 px-3 py-2 text-neutral-900 dark:border-neutral-700 dark:text-neutral-100" colSpan={2}>Quarter total</td>
              {isSpendMode ? (
                <td className="border border-neutral-300 px-3 py-2 text-right tabular-nums text-neutral-900 dark:border-neutral-700 dark:text-neutral-100">
                  {formatNumber(totals.amount)}
                </td>
              ) : null}
              <td className="border border-neutral-300 px-3 py-2 dark:border-neutral-700" />
              <td className="border border-neutral-300 px-3 py-2 text-right tabular-nums text-neutral-900 dark:border-neutral-700 dark:text-neutral-100">
                {formatNumber(totals.activity)}
              </td>
              <td className="border border-neutral-300 px-3 py-2 dark:border-neutral-700" />
              <td className="border border-neutral-300 px-3 py-2 text-right tabular-nums text-neutral-900 dark:border-neutral-700 dark:text-neutral-100">
                {formatNumber(totals.emissions)}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </article>
  );
}

function NumberCell({
  label,
  value,
  min,
  onChange,
}: {
  label: string;
  value: string;
  min: string;
  onChange: (value: string) => void;
}) {
  return (
    <input
      aria-label={label}
      type="number"
      min={min}
      step="any"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={inputClassName}
    />
  );
}

const inputClassName =
  'h-9 w-full rounded-md border border-neutral-300 bg-white px-2.5 text-right text-sm text-neutral-900 shadow-[inset_0_0_0_1px_rgba(229,229,229,0.8)] focus:outline-none focus:ring-2 focus:ring-primary-200 dark:border-neutral-600 dark:bg-neutral-900 dark:text-neutral-100 dark:shadow-[inset_0_0_0_1px_rgba(82,82,82,0.8)] dark:focus:ring-primary-800';

function SummaryPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-primary-200 bg-primary-50 px-3 py-2 text-right dark:border-primary-700/40 dark:bg-primary-900/30">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-primary-700 dark:text-primary-300">{label}</p>
      <p className="mt-0.5 text-sm font-semibold tabular-nums text-primary-900 dark:text-primary-100">{value}</p>
    </div>
  );
}

function activity(value: string): number {
  return Math.max(safeNumber(value), 0);
}

function safeNumber(value: string): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function rowActivity(config: BreakdownConfig, row: BreakdownRow): number {
  if (config.mode === 'spend') {
    return safeNumber(row.amount) / Math.max(safeNumber(row.unitPrice), 1);
  }
  return activity(row.activity);
}

function calculateBreakdown(config: BreakdownConfig, rows: BreakdownRow[]): BreakdownTotals {
  return rows.reduce(
    (totals, row) => {
      const activityValue = rowActivity(config, row);
      return {
        amount: totals.amount + safeNumber(row.amount),
        activity: totals.activity + activityValue,
        emissions: totals.emissions + activityValue * config.factor,
      };
    },
    { amount: 0, activity: 0, emissions: 0 },
  );
}

function formatInput(value: number): string {
  return value > 0 ? String(Number(value.toFixed(3))) : '';
}

function formatNumber(value: number): string {
  return value.toLocaleString(undefined, {
    maximumFractionDigits: 3,
    minimumFractionDigits: value > 0 && value < 1 ? 3 : 0,
  });
}
