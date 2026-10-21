'use client';

import {useTranslations} from 'next-intl';

import VinSegments from './VinSegments';
import type {VinStructure} from '@/lib/types';

function Row({label, children}: {label: string; children: React.ReactNode}) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1.5 text-sm">
      <span style={{color: 'var(--muted)'}}>{label}</span>
      <span className="text-right font-medium">{children}</span>
    </div>
  );
}

export default function StructurePanel({
  structure,
  vinMasked
}: {
  structure: VinStructure;
  vinMasked: string;
}) {
  const t = useTranslations('structure');

  const checkDigitNote = structure.check_digit_required
    ? structure.check_digit_valid
      ? t('checkDigitValid')
      : t('checkDigitInvalid')
    : t('checkDigitNotRequired');

  return (
    <section
      className="rounded-xl border p-5"
      style={{borderColor: 'var(--border)', background: 'var(--surface)'}}
    >
      <h2 className="text-sm font-semibold">{t('title')}</h2>
      <p className="mb-4 mt-1 text-xs leading-relaxed" style={{color: 'var(--muted)'}}>
        {t('explain')}
      </p>

      <VinSegments vinMasked={vinMasked} />

      <div className="mt-5 divide-y" style={{borderColor: 'var(--border)'}}>
        <Row label={t('country')}>
          {structure.country ?? '-'}
          {structure.country_code ? (
            <span className="ml-1 font-mono text-xs" style={{color: 'var(--muted)'}}>
              {structure.country_code}
            </span>
          ) : null}
        </Row>
        <Row label={t('checkDigit')}>
          <span className="font-mono">{structure.check_digit}</span>
          <span className="ml-2 text-xs font-normal" style={{color: 'var(--muted)'}}>
            {checkDigitNote}
          </span>
        </Row>
        <Row label={t('modelYearCode')}>
          <span className="font-mono">{structure.model_year_code}</span>
          {structure.model_year_candidates.length > 1 ? (
            <span className="ml-2 text-xs font-normal" style={{color: 'var(--warn)'}}>
              {t('modelYearCandidates')}: {structure.model_year_candidates.join(' / ')}
            </span>
          ) : null}
        </Row>
        <Row label={t('plantCode')}>
          <span className="font-mono">{structure.plant_code}</span>
        </Row>
        {structure.extended_wmi ? (
          <Row label={t('extendedWmi')}>
            <span className="font-mono">{structure.extended_wmi}</span>
          </Row>
        ) : null}
        <Row label={t('serialMasked')}>
          <span className="font-mono" style={{color: 'var(--muted)'}}>
            XXXXXX
          </span>
        </Row>
      </div>

      {structure.is_small_manufacturer ? (
        <p className="mt-3 text-xs" style={{color: 'var(--muted)'}}>
          {t('smallManufacturer')}
        </p>
      ) : null}
    </section>
  );
}
