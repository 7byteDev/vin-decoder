'use client';

import {useRouter} from 'next/navigation';

export type SortKey = 'count-desc' | 'count-asc' | 'name-asc' | 'name-desc';

/**
 * Sortierung der Markenuebersicht.
 *
 * Als Auswahlfeld und nicht als Schaltflaechenreihe: vier Optionen mit
 * Richtungsangabe werden nebeneinander zu breit, und ein Auswahlfeld ist
 * auf dem Telefon ohnehin bequemer.
 */
export default function BrandSort({
  locale,
  current,
  label,
  options
}: {
  locale: string;
  current: SortKey;
  label: string;
  options: {key: SortKey; text: string}[];
}) {
  const router = useRouter();

  return (
    <label className="flex items-center gap-2 text-xs">
      <span style={{color: 'var(--muted)'}}>{label}:</span>
      <select
        value={current}
        onChange={(event) => {
          const key = event.target.value;
          router.push(
            key === 'count-desc'
              ? `/${locale}/brands`
              : `/${locale}/brands?sort=${key}`
          );
        }}
        className="rounded-md border px-2 py-1.5 text-xs font-medium"
        style={{
          borderColor: 'var(--border)',
          background: 'var(--surface)',
          color: 'var(--text)'
        }}
      >
        {options.map((option) => (
          <option key={option.key} value={option.key}>
            {option.text}
          </option>
        ))}
      </select>
    </label>
  );
}
