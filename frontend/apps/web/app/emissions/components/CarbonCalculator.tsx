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

interface VehicleMonthRow {
  id: string;
  month: string;
  amountNaira: string;
  unitPricePerLitre: string;
}

const DEFAULT_SUMMARY_ROWS: SummaryRow[] = [
  { id: 'diesel-generator', source: 'Diesel generator fuel', unit: 'Litres', factor: 2.68, activity: '' },
  { id: 'company-vehicles', source: 'Company vehicles fuel', unit: 'Litres', factor: 2.31, activity: '' },
  { id: 'grid-electricity', source: 'Grid electricity', unit: 'kWh', factor: 0.5, activity: '' },
  { id: 'natural-gas', source: 'Natural gas', unit: 'm3', factor: 2, activity: '' },
];

const DEFAULT_VEHICLE_ROWS: VehicleMonthRow[] = [
  { id: 'jan', month: 'January', amountNaira: '167742.70', unitPricePerLitre: '1325' },
  { id: 'feb', month: 'February', amountNaira: '194134.00', unitPricePerLitre: '1325' },
  { id: 'mar', month: 'March', amountNaira: '251951.00', unitPricePerLitre: '1325' },
  { id: 'apr', month: 'April', amountNaira: '394899.00', unitPricePerLitre: '1325' },
];

const VEHICLE_FACTOR_KG_CO2_PER_LITRE = 2.31;

export function CarbonCalculator() {
  const [summaryRows, setSummaryRows] = useState(DEFAULT_SUMMARY_ROWS);
  const [vehicleRows, setVehicleRows] = useState(DEFAULT_VEHICLE_ROWS);

  const summaryTotal = useMemo(
    () => summaryRows.reduce((sum, row) => sum + activity(row.activity) * row.factor, 0),
    [summaryRows],
  );
  const vehicleTotals = useMemo(() => {
    return vehicleRows.reduce(
      (totals, row) => {
        const litres = safeNumber(row.amountNaira) / Math.max(safeNumber(row.unitPricePerLitre), 1);
        const emissions = litres * VEHICLE_FACTOR_KG_CO2_PER_LITRE;
        return {
          amountNaira: totals.amountNaira + safeNumber(row.amountNaira),
          litres: totals.litres + litres,
          emissions: totals.emissions + emissions,
        };
      },
      { amountNaira: 0, litres: 0, emissions: 0 },
    );
  }, [vehicleRows]);

  function updateSummary(id: string, activityValue: string) {
    setSummaryRows((rows) =>
      rows.map((row) => (row.id === id ? { ...row, activity: activityValue } : row)),
    );
  }

  function updateVehicle(id: string, patch: Partial<VehicleMonthRow>) {
    setVehicleRows((rows) =>
      rows.map((row) => (row.id === id ? { ...row, ...patch } : row)),
    );
  }

  return (
    <Card title="Carbon calculator" description="Quick CO2 worksheet for fuel, electricity, gas, and pool vehicle usage.">
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

          <div className="overflow-x-auto rounded-md border border-neutral-200 dark:border-neutral-800">
            <table className="min-w-full divide-y divide-neutral-200 text-sm dark:divide-neutral-800">
              <thead className="bg-neutral-50 text-xs uppercase tracking-wide text-neutral-500 dark:bg-neutral-900/60 dark:text-neutral-400">
                <tr>
                  <th scope="col" className="px-3 py-2 text-left">Source</th>
                  <th scope="col" className="px-3 py-2 text-left">Activity data</th>
                  <th scope="col" className="px-3 py-2 text-left">Unit</th>
                  <th scope="col" className="px-3 py-2 text-right">Emission factor</th>
                  <th scope="col" className="px-3 py-2 text-right">Total emissions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100 bg-white dark:divide-neutral-800 dark:bg-neutral-900/60">
                {summaryRows.map((row) => {
                  const total = activity(row.activity) * row.factor;
                  return (
                    <tr key={row.id}>
                      <td className="px-3 py-2 font-medium text-neutral-800 dark:text-neutral-100">{row.source}</td>
                      <td className="min-w-40 px-3 py-2">
                        <input
                          aria-label={`${row.source} activity data`}
                          type="number"
                          min="0"
                          step="any"
                          value={row.activity}
                          onChange={(e) => updateSummary(row.id, e.target.value)}
                          className="h-9 w-full rounded-lg border border-neutral-200 bg-white px-2.5 text-sm text-neutral-900 focus:outline-none focus:ring-2 focus:ring-primary-200 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-100 dark:focus:ring-primary-800"
                        />
                      </td>
                      <td className="px-3 py-2 text-neutral-600 dark:text-neutral-300">{row.unit}</td>
                      <td className="px-3 py-2 text-right tabular-nums text-neutral-800 dark:text-neutral-200">
                        {formatNumber(row.factor)}
                      </td>
                      <td className="px-3 py-2 text-right font-semibold tabular-nums text-neutral-900 dark:text-neutral-100">
                        {formatNumber(total)}
                      </td>
                    </tr>
                  );
                })}
                <tr className="bg-neutral-50 font-semibold dark:bg-neutral-900">
                  <td className="px-3 py-2 text-neutral-900 dark:text-neutral-100">Total emissions</td>
                  <td className="px-3 py-2" colSpan={3} />
                  <td className="px-3 py-2 text-right tabular-nums text-neutral-900 dark:text-neutral-100">
                    {formatNumber(summaryTotal)}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section aria-label="Company vehicle quarterly breakdown" className="space-y-2">
          <div className="flex flex-wrap items-end justify-between gap-2">
            <div>
              <h2 className="text-sm font-semibold uppercase tracking-wide text-neutral-700 dark:text-neutral-200">
                Company pool vehicle fuel usage / emission factor quarterly breakdown
              </h2>
              <p className="text-xs text-neutral-500 dark:text-neutral-400">
                Enter monthly spend and pump price; litres and CO2 emissions calculate automatically.
              </p>
            </div>
            <SummaryPill label="Vehicle emissions" value={`${formatNumber(vehicleTotals.emissions)} kgCO2`} />
          </div>

          <div className="overflow-x-auto rounded-md border border-neutral-200 dark:border-neutral-800">
            <table className="min-w-full divide-y divide-neutral-200 text-sm dark:divide-neutral-800">
              <thead className="bg-neutral-50 text-xs uppercase tracking-wide text-neutral-500 dark:bg-neutral-900/60 dark:text-neutral-400">
                <tr>
                  <th scope="col" className="px-3 py-2 text-left">Source</th>
                  <th scope="col" className="px-3 py-2 text-left">Month</th>
                  <th scope="col" className="px-3 py-2 text-right">Amount</th>
                  <th scope="col" className="px-3 py-2 text-right">Unit per litre</th>
                  <th scope="col" className="px-3 py-2 text-right">Total litres</th>
                  <th scope="col" className="px-3 py-2 text-right">Emission factor</th>
                  <th scope="col" className="px-3 py-2 text-right">CO2 emissions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100 bg-white dark:divide-neutral-800 dark:bg-neutral-900/60">
                {vehicleRows.map((row, index) => {
                  const litres = safeNumber(row.amountNaira) / Math.max(safeNumber(row.unitPricePerLitre), 1);
                  const emissions = litres * VEHICLE_FACTOR_KG_CO2_PER_LITRE;
                  return (
                    <tr key={row.id}>
                      <td className="px-3 py-2 font-medium text-neutral-800 dark:text-neutral-100">
                        {index === 0 ? 'Pool vehicle fuel' : ''}
                      </td>
                      <td className="px-3 py-2 text-neutral-700 dark:text-neutral-300">{row.month}</td>
                      <td className="min-w-36 px-3 py-2">
                        <input
                          aria-label={`${row.month} amount`}
                          type="number"
                          min="0"
                          step="any"
                          value={row.amountNaira}
                          onChange={(e) => updateVehicle(row.id, { amountNaira: e.target.value })}
                          className="h-9 w-full rounded-lg border border-neutral-200 bg-white px-2.5 text-right text-sm text-neutral-900 focus:outline-none focus:ring-2 focus:ring-primary-200 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-100 dark:focus:ring-primary-800"
                        />
                      </td>
                      <td className="min-w-32 px-3 py-2">
                        <input
                          aria-label={`${row.month} unit per litre`}
                          type="number"
                          min="1"
                          step="any"
                          value={row.unitPricePerLitre}
                          onChange={(e) => updateVehicle(row.id, { unitPricePerLitre: e.target.value })}
                          className="h-9 w-full rounded-lg border border-neutral-200 bg-white px-2.5 text-right text-sm text-neutral-900 focus:outline-none focus:ring-2 focus:ring-primary-200 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-100 dark:focus:ring-primary-800"
                        />
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums text-neutral-800 dark:text-neutral-200">
                        {formatNumber(litres)}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums text-neutral-800 dark:text-neutral-200">
                        {formatNumber(VEHICLE_FACTOR_KG_CO2_PER_LITRE)}
                      </td>
                      <td className="px-3 py-2 text-right font-semibold tabular-nums text-neutral-900 dark:text-neutral-100">
                        {formatNumber(emissions)}
                      </td>
                    </tr>
                  );
                })}
                <tr className="bg-neutral-50 font-semibold dark:bg-neutral-900">
                  <td className="px-3 py-2 text-neutral-900 dark:text-neutral-100" colSpan={2}>Quarter total</td>
                  <td className="px-3 py-2 text-right tabular-nums text-neutral-900 dark:text-neutral-100">
                    {formatNumber(vehicleTotals.amountNaira)}
                  </td>
                  <td className="px-3 py-2" />
                  <td className="px-3 py-2 text-right tabular-nums text-neutral-900 dark:text-neutral-100">
                    {formatNumber(vehicleTotals.litres)}
                  </td>
                  <td className="px-3 py-2" />
                  <td className="px-3 py-2 text-right tabular-nums text-neutral-900 dark:text-neutral-100">
                    {formatNumber(vehicleTotals.emissions)}
                  </td>
                </tr>
              </tbody>
            </table>
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

function formatNumber(value: number): string {
  return value.toLocaleString(undefined, {
    maximumFractionDigits: 3,
    minimumFractionDigits: value > 0 && value < 1 ? 3 : 0,
  });
}
