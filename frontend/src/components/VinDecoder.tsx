'use client';

import {useLocale, useTranslations} from 'next-intl';
import {useState} from 'react';

import ConfidenceBar from './ConfidenceBar';
import FieldTable from './FieldTable';
import StructurePanel from './StructurePanel';
import {DecodeError, decodeVin} from '@/lib/api';
import type {ApiError, DecodeResponse} from '@/lib/types';

const EXAMPLE = 'WVWZZZ1JZ3W386752';

export default function VinDecoder() {
  const t = useTranslations('result');
  const form = useTranslations('form');
  const errors = useTranslations('errors');
  const warnings = useTranslations('warnings');
  const locale = useLocale();

  const [vin, setVin] = useState('');
  const [result, setResult] = useState<DecodeResponse | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      setResult(await decodeVin(vin, locale));
    } catch (caught) {
      setResult(null);
      setError(
        caught instanceof DecodeError
          ? caught.payload
          : {code: 'network', message: '', detail: {}}
      );
    } finally {
      setLoading(false);
    }
  }

  function errorText(payload: ApiError) {
    if (!errors.has(payload.code)) return payload.message;
    return payload.code === 'vin_invalid_characters'
      ? errors(payload.code, {characters: (payload.detail.characters ?? []).join(', ')})
      : errors(payload.code);
  }

  return (
    <div className="space-y-6">
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
            disabled={loading || vin.trim().length === 0}
            className="rounded-lg px-5 py-2.5 text-sm font-medium text-white transition-opacity disabled:opacity-40"
            style={{background: 'var(--accent)'}}
          >
            {loading ? form('loading') : form('submit')}
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

      {error ? (
        <div
          className="rounded-xl border p-4 text-sm"
          style={{borderColor: 'var(--danger)', background: 'var(--surface)'}}
        >
          <p className="font-medium" style={{color: 'var(--danger)'}}>
            {errors('title')}
          </p>
          <p className="mt-1">{errorText(error)}</p>
          {error.detail.suggestion ? (
            <button
              type="button"
              onClick={() => setVin(error.detail.suggestion as string)}
              className="mt-2 underline underline-offset-2"
            >
              {errors('suggestion', {suggestion: error.detail.suggestion})}
            </button>
          ) : null}
        </div>
      ) : null}

      {result ? (
        <div className="space-y-6">
          <section
            className="rounded-xl border p-5"
            style={{borderColor: 'var(--border)', background: 'var(--surface)'}}
          >
            <div className="mb-4 flex items-center justify-between gap-4">
              <h2 className="text-sm font-semibold">{t('title')}</h2>
              <span
                className="rounded-full px-2.5 py-1 text-xs font-medium"
                style={{
                  background: result.status === 'ok' ? 'var(--accent-soft)' : 'var(--warn-soft)',
                  color: result.status === 'ok' ? 'var(--accent)' : 'var(--warn)'
                }}
              >
                {t(`status.${result.status}`)}
              </span>
            </div>
            <ConfidenceBar value={result.confidence} label={t('confidence')} />
            <p className="mt-2 text-xs" style={{color: 'var(--muted)'}}>
              {t('durationMs', {ms: result.duration_ms})} &middot; {result.sources_used.join(', ')}
            </p>
          </section>

          <FieldTable fields={result.fields} locale={locale} />

          {result.warnings.length > 0 ? (
            <section
              className="rounded-xl border p-5"
              style={{borderColor: 'var(--border)', background: 'var(--surface)'}}
            >
              <h2 className="mb-2 text-sm font-semibold">{warnings('title')}</h2>
              <ul className="space-y-1.5 text-sm" style={{color: 'var(--muted)'}}>
                {result.warnings.map((code) => (
                  <li key={code}>{warnings.has(code) ? warnings(code) : code}</li>
                ))}
              </ul>
            </section>
          ) : null}

          <StructurePanel structure={result.structure} vinMasked={result.vin_masked} />
        </div>
      ) : (
        <p className="text-sm" style={{color: 'var(--muted)'}}>
          {t('empty')}
        </p>
      )}
    </div>
  );
}
