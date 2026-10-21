'use client';

import {useTranslations} from 'next-intl';
import {useState} from 'react';

import type {CountryRange, ModelYearCode} from '@/lib/server-api';

/**
 * Modelljahr-Codes.
 *
 * Die Daten kommen aus der API und damit aus derselben Konstante, die auch
 * die Decodierung verwendet - die Tabelle kann also nicht veralten, ohne
 * dass sich das Verhalten des Decoders mit ändert.
 */
export function ModelYearTable({codes}: {codes: ModelYearCode[]}) {
  const t = useTranslations('home.yearTable');

  return (
    <section
      className="rounded-xl border p-5 sm:p-6"
      style={{borderColor: 'var(--border)', background: 'var(--surface)'}}
    >
      <h2 className="text-base font-semibold">{t('title')}</h2>
      <p className="mb-4 mt-1.5 text-xs leading-relaxed" style={{color: 'var(--muted)'}}>
        {t('body')}
      </p>
      <div className="grid grid-cols-3 gap-1.5 sm:grid-cols-5 lg:grid-cols-6">
        {codes.map((entry) => (
          <div
            key={entry.code}
            className="rounded-lg border px-2.5 py-2 text-center"
            style={{borderColor: 'var(--border)', background: 'var(--surface-2)'}}
          >
            <div className="font-mono text-base font-semibold" style={{color: 'var(--primary)'}}>
              {entry.code}
            </div>
            <div className="text-[11px] leading-tight" style={{color: 'var(--muted)'}}>
              {entry.years[0]}
              <br />
              {entry.years[1]}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

const REGION_COLORS: Record<string, string> = {
  EU: 'var(--primary)',
  AS: 'var(--accent)',
  NA: 'var(--good)',
  AF: 'var(--muted)',
  OC: 'var(--muted)',
  SA: 'var(--muted)'
};

/** Länderbereiche der Herstellerkennung, zunächst gekürzt. */
export function CountryTable({ranges}: {ranges: CountryRange[]}) {
  const t = useTranslations('home.countryTable');
  const [expanded, setExpanded] = useState(false);

  // Europa zuerst - das ist der Schwerpunkt des Projekts
  const sorted = [...ranges].sort((a, b) => {
    const weight = (r: CountryRange) => (r.region_code === 'EU' ? 0 : 1);
    return weight(a) - weight(b);
  });
  const visible = expanded ? sorted : sorted.slice(0, 18);

  return (
    <section
      className="rounded-xl border p-5 sm:p-6"
      style={{borderColor: 'var(--border)', background: 'var(--surface)'}}
    >
      <h2 className="text-base font-semibold">{t('title')}</h2>
      <p className="mb-4 mt-1.5 text-xs leading-relaxed" style={{color: 'var(--muted)'}}>
        {t('body')}
      </p>

      <div className="scroll-x">
        <table className="zebra w-full text-sm">
          <thead>
            <tr className="text-left text-xs" style={{color: 'var(--muted)'}}>
              <th className="px-3 py-2 font-medium">{t('range')}</th>
              <th className="px-3 py-2 font-medium">{t('country')}</th>
              <th className="px-3 py-2 font-medium">{t('region')}</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((entry) => (
              <tr key={entry.range} className="border-t" style={{borderColor: 'var(--border)'}}>
                <td className="whitespace-nowrap px-3 py-2 font-mono text-xs">{entry.range}</td>
                <td className="px-3 py-2">
                  {entry.country}
                  {entry.country_code ? (
                    <span className="ml-1.5 text-xs" style={{color: 'var(--muted)'}}>
                      {entry.country_code}
                    </span>
                  ) : null}
                </td>
                <td className="px-3 py-2">
                  <span
                    className="rounded-md px-2 py-0.5 text-xs font-medium"
                    style={{
                      color: REGION_COLORS[entry.region_code ?? ''] ?? 'var(--muted)',
                      background: 'var(--surface-2)'
                    }}
                  >
                    {entry.region}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {sorted.length > 18 ? (
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="mt-3 text-xs font-medium underline underline-offset-2"
          style={{color: 'var(--primary)'}}
        >
          {expanded ? t('showLess') : t('showAll', {count: sorted.length})}
        </button>
      ) : null}
    </section>
  );
}
