import Link from 'next/link';
import {getTranslations} from 'next-intl/server';

import {fetchRecent} from '@/lib/server-api';

/**
 * Zuletzt gesuchte Fahrzeuge.
 *
 * Angezeigt wird die maskierte VIN - Position 1-11 plus Maske. Der
 * Seriennummernblock existiert im Log gar nicht, es gibt hier also nichts
 * zu verbergen, was nicht ohnehin schon weg waere.
 */
export default async function RecentSearches({locale}: {locale: string}) {
  const t = await getTranslations({locale, namespace: 'home.recent'});
  const entries = (await fetchRecent(12)) ?? [];

  if (entries.length === 0) return null;

  return (
    <section>
      <h2 className="mb-3 text-base font-semibold">{t('title')}</h2>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {entries.map((entry) => {
          const prefix = entry.vin_masked.replace(/X+$/, '');
          const name = [entry.make, entry.model].filter(Boolean).join(' ');
          return (
            <Link
              key={entry.vin_masked}
              href={`/${locale}/vin/${prefix}`}
              className="group flex items-center justify-between gap-3 rounded-lg border px-3.5 py-2.5 transition-colors"
              style={{
                borderColor: 'var(--border)',
                background: 'var(--surface)',
                boxShadow: 'var(--shadow-sm)'
              }}
            >
              <span className="min-w-0">
                <span className="block truncate text-sm font-medium">
                  {name || entry.vin_masked}
                </span>
                <span
                  className="mt-0.5 block font-mono text-[11px] tracking-wide"
                  style={{color: 'var(--muted)'}}
                >
                  {prefix}
                  <span style={{opacity: 0.45}}>{entry.vin_masked.slice(prefix.length)}</span>
                </span>
              </span>
              {entry.model_year ? (
                <span
                  className="shrink-0 rounded-md px-2 py-1 text-xs font-medium"
                  style={{background: 'var(--primary-soft)', color: 'var(--primary)'}}
                >
                  {entry.model_year}
                </span>
              ) : null}
            </Link>
          );
        })}
      </div>
      <p className="mt-3 text-xs" style={{color: 'var(--muted)'}}>
        {t('note')}
      </p>
    </section>
  );
}
