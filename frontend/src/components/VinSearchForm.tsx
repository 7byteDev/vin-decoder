'use client';

import {useLocale, useTranslations} from 'next-intl';
import {useRouter} from 'next/navigation';
import {useState, useTransition} from 'react';

const EXAMPLE = 'WVWZZZ1JZ3W386752';

/**
 * Sucheingabe. Fuehrt auf /{locale}/vin/{vin} - eigene Adresse je VIN,
 * damit Ergebnisse verlinkbar und fuer Suchmaschinen auffindbar sind.
 */
export default function VinSearchForm({initialVin = ''}: {initialVin?: string}) {
  const form = useTranslations('form');
  const locale = useLocale();
  const router = useRouter();
  const [vin, setVin] = useState(initialVin);
  const [pending, startTransition] = useTransition();

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const cleaned = vin.trim().toUpperCase().replace(/[\s-]/g, '');
    if (cleaned.length < 10) return;
    startTransition(() => router.push(`/${locale}/vin/${encodeURIComponent(cleaned)}`));
  }

  return (
    <form onSubmit={submit} className="space-y-2">
      <label htmlFor="vin" className="block text-sm font-medium">
        {form('label')}
      </label>
      <div className="flex flex-col gap-2 sm:flex-row">
        <input
          id="vin"
          name="vin"
          value={vin}
          onChange={(event) => setVin(event.target.value.toUpperCase())}
          placeholder={form('placeholder')}
          spellCheck={false}
          autoComplete="off"
          maxLength={24}
          className="flex-1 rounded-lg border px-3.5 py-2.5 font-mono text-base tracking-[0.12em] outline-none focus:ring-2"
          style={{
            borderColor: 'var(--border)',
            background: 'var(--surface)',
            color: 'var(--text)'
          }}
        />
        <button
          type="submit"
          disabled={pending || vin.trim().length < 10}
          className="rounded-lg px-5 py-2.5 text-sm font-medium text-white transition-opacity disabled:opacity-40"
          style={{background: 'var(--accent)'}}
        >
          {pending ? form('loading') : form('submit')}
        </button>
      </div>
      <div className="flex flex-wrap items-center gap-3 text-xs" style={{color: 'var(--muted)'}}>
        <span>{form('hint')}</span>
        <button
          type="button"
          onClick={() => setVin(EXAMPLE)}
          className="underline underline-offset-2"
        >
          {form('example')}
        </button>
      </div>
    </form>
  );
}
