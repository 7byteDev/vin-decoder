import {useTranslations} from 'next-intl';

import type {ConsumptionRow, EmissionRow} from '@/lib/types';

/** Farbskala der Schweizer Energieeffizienzkategorien A (gut) bis G. */
const EFFICIENCY_COLORS: Record<string, string> = {
  A: '#0f8a4d',
  B: '#4aa72e',
  C: '#8cbb1f',
  D: '#e0c020',
  E: '#e59a1c',
  F: '#dd6f1c',
  G: '#c93a2a'
};

function label(values: ReturnType<typeof useTranslations>, group: string, raw: string | null) {
  if (!raw) return null;
  const key = `${group}.${raw}`;
  return values.has(key) ? values(key) : raw;
}

export default function ConsumptionEmissions({
  consumption,
  emissions
}: {
  consumption: ConsumptionRow[];
  emissions: EmissionRow[];
}) {
  const t = useTranslations('detail');
  const units = useTranslations('units');
  const values = useTranslations('values');

  if (consumption.length === 0 && emissions.length === 0) {
    return (
      <p className="text-xs" style={{color: 'var(--muted)'}}>
        {t('noExtras')}
      </p>
    );
  }

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {consumption.length > 0 ? (
        <section
          className="rounded-xl border p-5"
          style={{borderColor: 'var(--border)', background: 'var(--surface)'}}
        >
          <h2 className="mb-3 text-sm font-semibold">{t('consumption')}</h2>
          <div className="space-y-3">
            {consumption.map((row, index) => (
              <div
                key={index}
                className="rounded-lg border p-3"
                style={{borderColor: 'var(--border)', background: 'var(--surface-2)'}}
              >
                <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
                  {row.transmission ? (
                    <span className="font-medium">{label(values, 'transmission', row.transmission)}</span>
                  ) : null}
                  {row.fuel_type ? (
                    <span style={{color: 'var(--muted)'}}>{label(values, 'fuel', row.fuel_type)}</span>
                  ) : null}
                  {row.efficiency_category ? (
                    <span
                      className="ml-auto rounded px-2 py-0.5 font-bold text-white"
                      style={{
                        background: EFFICIENCY_COLORS[row.efficiency_category] ?? 'var(--muted)'
                      }}
                      title={t('efficiency')}
                    >
                      {row.efficiency_category}
                    </span>
                  ) : null}
                </div>
                <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
                  {row.consumption_l100 ? (
                    <div className="flex justify-between gap-2">
                      <dt style={{color: 'var(--muted)'}}>{t('nedc')}</dt>
                      <dd className="font-medium">{row.consumption_l100} l/100 km</dd>
                    </div>
                  ) : null}
                  {row.co2_g_km ? (
                    <div className="flex justify-between gap-2">
                      <dt style={{color: 'var(--muted)'}}>CO₂</dt>
                      <dd className="font-medium">{row.co2_g_km} g/km</dd>
                    </div>
                  ) : null}
                  {row.consumption_wltp_l100 ? (
                    <div className="flex justify-between gap-2">
                      <dt style={{color: 'var(--muted)'}}>{t('wltp')}</dt>
                      <dd className="font-medium">{row.consumption_wltp_l100} l/100 km</dd>
                    </div>
                  ) : null}
                  {row.co2_wltp_g_km ? (
                    <div className="flex justify-between gap-2">
                      <dt style={{color: 'var(--muted)'}}>CO₂ {t('wltp')}</dt>
                      <dd className="font-medium">{row.co2_wltp_g_km} g/km</dd>
                    </div>
                  ) : null}
                  {row.electric_kwh100 ? (
                    <div className="flex justify-between gap-2">
                      <dt style={{color: 'var(--muted)'}}>kWh</dt>
                      <dd className="font-medium">{row.electric_kwh100} kWh/100 km</dd>
                    </div>
                  ) : null}
                  {row.electric_range_km ? (
                    <div className="flex justify-between gap-2">
                      <dt style={{color: 'var(--muted)'}}>{t('range')}</dt>
                      <dd className="font-medium">
                        {row.electric_range_km} {units('kmh').replace('/h', '')}
                      </dd>
                    </div>
                  ) : null}
                </dl>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {emissions.length > 0 ? (
        <section
          className="rounded-xl border p-5"
          style={{borderColor: 'var(--border)', background: 'var(--surface)'}}
        >
          <h2 className="mb-3 text-sm font-semibold">{t('emissions')}</h2>
          <div className="space-y-3">
            {emissions.map((row, index) => (
              <div
                key={index}
                className="rounded-lg border p-3"
                style={{borderColor: 'var(--border)', background: 'var(--surface-2)'}}
              >
                <div className="mb-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
                  {row.emission_code ? (
                    <span>
                      <span style={{color: 'var(--muted)'}}>{t('emissionCode')} </span>
                      <span className="font-mono font-semibold">{row.emission_code}</span>
                    </span>
                  ) : null}
                  {row.exhaust_code ? (
                    <span>
                      <span style={{color: 'var(--muted)'}}>{t('exhaustCode')} </span>
                      <span className="font-mono">{row.exhaust_code}</span>
                    </span>
                  ) : null}
                  {row.transmission ? (
                    <span className="ml-auto" style={{color: 'var(--muted)'}}>
                      {label(values, 'transmission', row.transmission)}
                    </span>
                  ) : null}
                </div>
                {Object.keys(row.pollutants).length > 0 ? (
                  <>
                    <div className="mb-1 text-[11px]" style={{color: 'var(--muted)'}}>
                      {t('pollutants')}
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {Object.entries(row.pollutants).map(([key, value]) => (
                        <span
                          key={key}
                          className="rounded px-2 py-0.5 text-xs"
                          style={{background: 'var(--surface)', color: 'var(--text-soft)'}}
                        >
                          <span style={{color: 'var(--muted)'}}>{key.replace('ET-', '')}</span>{' '}
                          <span className="font-medium">{value}</span>
                        </span>
                      ))}
                    </div>
                  </>
                ) : null}
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
