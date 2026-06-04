'use client';

import { useState, type FormEvent } from 'react';

import { Banner, Button, Card, Input, Select } from '@petrobrain/ui';

import type { InventoryRequest, SourceType } from '@/lib/emissions/types';

const GWP_SETS = [
  { value: 'AR6', label: 'IPCC AR6 (default)' },
  { value: 'AR5', label: 'IPCC AR5' },
  { value: 'AR4', label: 'IPCC AR4' },
];
const TARGET_TIERS = [
  { value: 'Tier 3', label: 'Tier 3 - measurement-based' },
  { value: 'Tier 2', label: 'Tier 2 - factor-based' },
  { value: 'Tier 1', label: 'Tier 1 - default factors' },
];
const SOURCE_TYPES: Array<{ value: SourceType; label: string }> = [
  { value: 'flaring', label: 'Flaring' },
  { value: 'venting', label: 'Venting' },
  { value: 'fugitive_t2', label: 'Fugitive emissions - component counts' },
  { value: 'fugitive_t3', label: 'Fugitive emissions - measured leak rate' },
  { value: 'combustion', label: 'Combustion' },
];

interface SourceDraft {
  id: string;
  label: string;
  type: SourceType;
  gasVolumeScf: string;
  methaneFractionPct: string;
  combustionEfficiencyPct: string;
  measured: boolean;
  componentCount: string;
  operatingHours: string;
  measuredLeakKgPerHr: string;
  fuelScf: string;
  co2KgPerScf: string;
  ch4KgPerScf: string;
  n2oKgPerScf: string;
}

export interface InventoryBuilderProps {
  defaultFacility?: string;
  defaultPeriod?: string;
  defaultOperator?: string;
  defaultAsset?: string;
  pending: boolean;
  error: string | null;
  onSubmit: (request: InventoryRequest) => void;
  onCancel: () => void;
}

let draftCounter = 1;

function newSource(overrides: Partial<SourceDraft> = {}): SourceDraft {
  draftCounter += 1;
  return {
    id: `source-${Date.now()}-${draftCounter}`,
    label: 'FL-1',
    type: 'flaring',
    gasVolumeScf: '1000000',
    methaneFractionPct: '100',
    combustionEfficiencyPct: '98',
    measured: true,
    componentCount: '100',
    operatingHours: '8760',
    measuredLeakKgPerHr: '0.5',
    fuelScf: '100000',
    co2KgPerScf: '0.054',
    ch4KgPerScf: '0',
    n2oKgPerScf: '0',
    ...overrides,
  };
}

/**
 * Phase-1 inventory builder.
 *
 * The API still receives a structured source list, but the visible UI uses
 * source categories and measurement fields so engineers do not have to edit
 * payload keys or raw objects.
 */
export function InventoryBuilder({
  defaultFacility = '',
  defaultPeriod = '',
  defaultOperator = '',
  defaultAsset = '',
  pending,
  error,
  onSubmit,
  onCancel,
}: InventoryBuilderProps) {
  const [facility, setFacility] = useState(defaultFacility);
  const [period, setPeriod] = useState(defaultPeriod);
  const [operator, setOperator] = useState(defaultOperator);
  const [asset, setAsset] = useState(defaultAsset);
  const [gwpSet, setGwpSet] = useState('AR6');
  const [targetTier, setTargetTier] = useState('Tier 3');
  const [sources, setSources] = useState<SourceDraft[]>([newSource()]);
  const [formError, setFormError] = useState<string | null>(null);

  function submit(e: FormEvent) {
    e.preventDefault();
    setFormError(null);

    const converted: InventoryRequest['sources'] = [];
    for (const source of sources) {
      const next = toInventorySource(source);
      if ('error' in next) {
        setFormError(next.error);
        return;
      }
      converted.push(next);
    }

    const request: InventoryRequest = {
      facility_id: facility.trim(),
      period: period.trim(),
      operator: operator.trim(),
      asset: asset.trim() || null,
      gwp_set: gwpSet,
      target_tier: targetTier,
      sources: converted,
    };
    onSubmit(request);
  }

  function updateSource(id: string, patch: Partial<SourceDraft>) {
    setSources((current) =>
      current.map((source) => (source.id === id ? { ...source, ...patch } : source)),
    );
  }

  function addSource() {
    const index = sources.length + 1;
    setSources((current) => [
      ...current,
      newSource({ label: `SRC-${index}`, measured: targetTier === 'Tier 3' }),
    ]);
  }

  function removeSource(id: string) {
    setSources((current) => (current.length === 1 ? current : current.filter((source) => source.id !== id)));
  }

  return (
    <Card title="Generate inventory" description="Build a filing-ready GHGEMP report from facility source data.">
      <form className="space-y-4" onSubmit={submit}>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <Input
            label="Facility ID"
            placeholder="FAC-1"
            value={facility}
            onChange={(e) => setFacility(e.target.value)}
            required
            disabled={pending}
          />
          <Input
            label="Period"
            placeholder="2026-Q3"
            hint="YYYY-Qn for quarterly filings."
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            required
            disabled={pending}
          />
          <Input
            label="Operator"
            placeholder="Operator name"
            value={operator}
            onChange={(e) => setOperator(e.target.value)}
            required
            disabled={pending}
          />
          <Input
            label="Asset"
            placeholder="OML-99 (optional)"
            value={asset}
            onChange={(e) => setAsset(e.target.value)}
            disabled={pending}
          />
          <Select
            label="GWP set"
            value={gwpSet}
            onChange={(e) => setGwpSet(e.target.value)}
            options={GWP_SETS}
            disabled={pending}
          />
          <Select
            label="Target tier"
            value={targetTier}
            onChange={(e) => setTargetTier(e.target.value)}
            options={TARGET_TIERS}
            disabled={pending}
          />
        </div>

        <section className="space-y-2" aria-label="Emission sources">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h3 className="text-sm font-semibold text-neutral-800 dark:text-neutral-100">Emission sources</h3>
              <p className="text-xs text-neutral-500 dark:text-neutral-400">
                Add each facility source and its activity data. PetroBrain formats the filing record behind the scenes.
              </p>
            </div>
            <Button type="button" variant="secondary" size="sm" onClick={addSource} disabled={pending}>
              Add source
            </Button>
          </div>

          <div className="space-y-3">
            {sources.map((source, index) => (
              <SourceEditor
                key={source.id}
                source={source}
                index={index}
                pending={pending}
                canRemove={sources.length > 1}
                onChange={(patch) => updateSource(source.id, patch)}
                onRemove={() => removeSource(source.id)}
              />
            ))}
          </div>
        </section>

        {formError ? (
          <Banner tone="danger" title="Check source data">
            {formError}
          </Banner>
        ) : null}

        {error ? (
          <Banner tone="danger" title="Could not generate report">
            Review the facility details and source measurements, then try again.
          </Banner>
        ) : null}

        <div className="flex items-center justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onCancel} disabled={pending}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={pending} loading={pending}>
            Generate GHGEMP report
          </Button>
        </div>
      </form>
    </Card>
  );
}

function SourceEditor({
  source,
  index,
  pending,
  canRemove,
  onChange,
  onRemove,
}: {
  source: SourceDraft;
  index: number;
  pending: boolean;
  canRemove: boolean;
  onChange: (patch: Partial<SourceDraft>) => void;
  onRemove: () => void;
}) {
  return (
    <article className="rounded-xl border border-neutral-200 bg-neutral-50/60 p-3 dark:border-neutral-700 dark:bg-neutral-900/60">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-semibold text-neutral-800 dark:text-neutral-100">Source {index + 1}</p>
        {canRemove ? (
          <Button type="button" variant="ghost" size="sm" onClick={onRemove} disabled={pending}>
            Remove
          </Button>
        ) : null}
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <Input
          label="Source tag"
          placeholder="FL-1"
          value={source.label}
          onChange={(e) => onChange({ label: e.target.value })}
          required
          disabled={pending}
        />
        <Select
          label="Category"
          value={source.type}
          onChange={(e) => onChange({ type: e.target.value as SourceType })}
          options={SOURCE_TYPES}
          disabled={pending}
        />

        {source.type === 'flaring' || source.type === 'venting' ? (
          <>
            <Input
              label="Gas volume"
              type="number"
              min="0"
              step="any"
              unit="scf"
              value={source.gasVolumeScf}
              onChange={(e) => onChange({ gasVolumeScf: e.target.value })}
              required
              disabled={pending}
            />
            <Input
              label="Methane in gas"
              type="number"
              min="0"
              max="100"
              step="any"
              unit="%"
              value={source.methaneFractionPct}
              onChange={(e) => onChange({ methaneFractionPct: e.target.value })}
              required
              disabled={pending}
            />
            {source.type === 'flaring' ? (
              <Input
                label="Combustion efficiency"
                type="number"
                min="0"
                max="100"
                step="any"
                unit="%"
                value={source.combustionEfficiencyPct}
                onChange={(e) => onChange({ combustionEfficiencyPct: e.target.value })}
                required
                disabled={pending}
              />
            ) : null}
          </>
        ) : null}

        {source.type === 'fugitive_t2' ? (
          <>
            <Input
              label="Component count"
              type="number"
              min="0"
              step="1"
              hint="Use total counted valves/components for this source area."
              value={source.componentCount}
              onChange={(e) => onChange({ componentCount: e.target.value })}
              required
              disabled={pending}
            />
            <Input
              label="Operating hours"
              type="number"
              min="0"
              step="any"
              unit="hr"
              value={source.operatingHours}
              onChange={(e) => onChange({ operatingHours: e.target.value })}
              required
              disabled={pending}
            />
          </>
        ) : null}

        {source.type === 'fugitive_t3' ? (
          <>
            <Input
              label="Measured leak rate"
              type="number"
              min="0"
              step="any"
              unit="kg/hr"
              value={source.measuredLeakKgPerHr}
              onChange={(e) => onChange({ measuredLeakKgPerHr: e.target.value })}
              required
              disabled={pending}
            />
            <Input
              label="Operating hours"
              type="number"
              min="0"
              step="any"
              unit="hr"
              value={source.operatingHours}
              onChange={(e) => onChange({ operatingHours: e.target.value })}
              required
              disabled={pending}
            />
          </>
        ) : null}

        {source.type === 'combustion' ? (
          <>
            <Input
              label="Fuel gas"
              type="number"
              min="0"
              step="any"
              unit="scf"
              value={source.fuelScf}
              onChange={(e) => onChange({ fuelScf: e.target.value })}
              required
              disabled={pending}
            />
            <Input
              label="CO2 factor"
              type="number"
              min="0"
              step="any"
              unit="kg/scf"
              value={source.co2KgPerScf}
              onChange={(e) => onChange({ co2KgPerScf: e.target.value })}
              required
              disabled={pending}
            />
            <Input
              label="CH4 factor"
              type="number"
              min="0"
              step="any"
              unit="kg/scf"
              value={source.ch4KgPerScf}
              onChange={(e) => onChange({ ch4KgPerScf: e.target.value })}
              disabled={pending}
            />
            <Input
              label="N2O factor"
              type="number"
              min="0"
              step="any"
              unit="kg/scf"
              value={source.n2oKgPerScf}
              onChange={(e) => onChange({ n2oKgPerScf: e.target.value })}
              disabled={pending}
            />
          </>
        ) : null}
      </div>

      {source.type !== 'fugitive_t2' ? (
        <label className="mt-3 flex items-center gap-2 text-sm text-neutral-700 dark:text-neutral-300">
          <input
            type="checkbox"
            checked={source.measured}
            onChange={(e) => onChange({ measured: e.target.checked })}
            disabled={pending}
            className="h-4 w-4 rounded border-neutral-300 text-primary-600 focus:ring-primary-400"
          />
          Measurement-based data available
        </label>
      ) : null}
    </article>
  );
}

function toInventorySource(source: SourceDraft): InventoryRequest['sources'][number] | { error: string } {
  const sourceId = source.label.trim();
  if (!sourceId) return { error: 'Each source needs a source tag.' };

  if (source.type === 'flaring' || source.type === 'venting') {
    const gasVolumeScf = positiveNumber(source.gasVolumeScf);
    const methaneFractionPct = boundedNumber(source.methaneFractionPct, 0, 100);
    if (gasVolumeScf === null) return { error: `${sourceId}: enter gas volume greater than zero.` };
    if (methaneFractionPct === null) return { error: `${sourceId}: methane in gas must be between 0 and 100%.` };

    const params: Record<string, unknown> = {
      gas_volume_scf: gasVolumeScf,
      composition: { CH4: methaneFractionPct / 100 },
      measured: source.measured,
    };
    if (source.type === 'flaring') {
      const efficiency = boundedNumber(source.combustionEfficiencyPct, 0, 100);
      if (efficiency === null) return { error: `${sourceId}: combustion efficiency must be between 0 and 100%.` };
      params['combustion_efficiency'] = efficiency / 100;
    }
    return { source_id: sourceId, source_type: source.type, params };
  }

  if (source.type === 'fugitive_t2') {
    const componentCount = positiveNumber(source.componentCount);
    const operatingHours = positiveNumber(source.operatingHours);
    if (componentCount === null) return { error: `${sourceId}: enter component count greater than zero.` };
    if (operatingHours === null) return { error: `${sourceId}: enter operating hours greater than zero.` };
    return {
      source_id: sourceId,
      source_type: source.type,
      params: {
        component_counts: { valve: Math.round(componentCount) },
        operating_hours: operatingHours,
      },
    };
  }

  if (source.type === 'fugitive_t3') {
    const leakRate = positiveNumber(source.measuredLeakKgPerHr);
    const operatingHours = positiveNumber(source.operatingHours);
    if (leakRate === null) return { error: `${sourceId}: enter measured leak rate greater than zero.` };
    if (operatingHours === null) return { error: `${sourceId}: enter operating hours greater than zero.` };
    return {
      source_id: sourceId,
      source_type: source.type,
      params: {
        measured_leaks_kg_ch4_per_hr: [leakRate],
        operating_hours: operatingHours,
      },
    };
  }

  const fuelScf = positiveNumber(source.fuelScf);
  const co2KgPerScf = nonNegativeNumber(source.co2KgPerScf);
  const ch4KgPerScf = nonNegativeNumber(source.ch4KgPerScf || '0');
  const n2oKgPerScf = nonNegativeNumber(source.n2oKgPerScf || '0');
  if (fuelScf === null) return { error: `${sourceId}: enter fuel gas greater than zero.` };
  if (co2KgPerScf === null || ch4KgPerScf === null || n2oKgPerScf === null) {
    return { error: `${sourceId}: emission factors must be zero or greater.` };
  }
  return {
    source_id: sourceId,
    source_type: source.type,
    params: {
      fuel_scf: fuelScf,
      co2_kg_per_scf: co2KgPerScf,
      ch4_kg_per_scf: ch4KgPerScf,
      n2o_kg_per_scf: n2oKgPerScf,
      measured: source.measured,
    },
  };
}

function positiveNumber(value: string): number | null {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function nonNegativeNumber(value: string): number | null {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : null;
}

function boundedNumber(value: string, min: number, max: number): number | null {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= min && parsed <= max ? parsed : null;
}
