import Link from 'next/link';
import {useTranslations} from 'next-intl';

import type {VehicleMatch} from '@/lib/types';

/** Übersetzt einen kanonischen Wert, faellt sonst auf den Rohwert zurueck. */
function useValueLabel() {
  const values = useTranslations('values');
  return (group: 'fuel' | 'transmission' | 'drive', raw: string | null) => {
    if (!raw) return null;
    const key = `${group}.${raw}`;
    return values.has(key) ? values(key) : raw;
  };
}

/**
 * Trefferliste: eine VIN trifft in der Regel mehrere Motorisierungen
 * derselben Baureihe. Gruppiert nach Marke und Baureihe, damit die
 * Auswahl uebersichtlich bleibt.
 */
export default function MatchTable({
  matches,
  vin,
  locale
}: {
  matches: VehicleMatch[];
  vin: string;
  locale: string;
}) {
  const t = useTranslations('list');
  const units = useTranslations('units');
  const label = useValueLabel();

  const groups = new Map<string, VehicleMatch[]>();
  for (const match of matches) {
    const family = [match.make, (match.model ?? '').split(' ')[0]].filter(Boolean).join(' · ');
    const existing = groups.get(family);
    if (existing) existing.push(match);
    else groups.set(family, [match]);
  }

  return (
    <div className="space-y-6">
      {[...groups.entries()].map(([family, rows]) => (
        <section key={family}>
          <h3 className="mb-2 flex items-baseline gap-2 text-sm font-semibold">
            {family}
            <span className="text-xs font-normal" style={{color: 'var(--muted)'}}>
              {rows.length}
            </span>
          </h3>
          <div
            className="overflow-x-auto rounded-xl border"
            style={{borderColor: 'var(--border)', background: 'var(--surface)'}}
          >
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs" style={{color: 'var(--muted)'}}>
                  <th className="px-4 py-2.5 font-medium">{t('model')}</th>
                  <th className="px-4 py-2.5 font-medium">{t('year')}</th>
                  <th className="px-4 py-2.5 font-medium">{t('power')}</th>
                  <th className="px-4 py-2.5 font-medium">{t('fuel')}</th>
                  <th className="hidden px-4 py-2.5 font-medium sm:table-cell">
                    {t('transmission')}
                  </th>
                  <th className="px-4 py-2.5" />
                </tr>
              </thead>
              <tbody>
                {rows.map((match) => (
                  <tr
                    key={match.id}
                    className="border-t"
                    style={{borderColor: 'var(--border)'}}
                  >
                    <td className="px-4 py-3 font-medium">
                      {match.model}
                      {match.displacement_ccm ? (
                        <span
                          className="ml-2 text-xs font-normal"
                          style={{color: 'var(--muted)'}}
                        >
                          {match.displacement_ccm} {units('ccm')}
                        </span>
                      ) : null}
                    </td>
                    <td className="px-4 py-3" style={{color: 'var(--muted)'}}>
                      {match.year ?? '–'}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3">
                      {match.power_kw ? (
                        <>
                          {match.power_ps} {units('ps')}
                          <span className="ml-1 text-xs" style={{color: 'var(--muted)'}}>
                            ({match.power_kw} {units('kw')})
                          </span>
                        </>
                      ) : (
                        '–'
                      )}
                    </td>
                    <td className="px-4 py-3">{label('fuel', match.fuel_type) ?? '–'}</td>
                    <td className="hidden px-4 py-3 sm:table-cell">
                      {label('transmission', match.transmission) ?? '–'}
                      {match.gears ? (
                        <span className="ml-1 text-xs" style={{color: 'var(--muted)'}}>
                          {units('gears', {count: match.gears})}
                        </span>
                      ) : null}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        href={`/${locale}/vin/${vin}/${match.id}`}
                        className="whitespace-nowrap rounded-md px-3 py-1.5 text-xs font-medium"
                        style={{background: 'var(--accent-soft)', color: 'var(--accent)'}}
                      >
                        {t('select')} →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}
    </div>
  );
}
