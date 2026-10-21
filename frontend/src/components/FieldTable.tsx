'use client';

import {useTranslations} from 'next-intl';

import ConfidenceBar from './ConfidenceBar';
import type {FieldResult} from '@/lib/types';

/** Reihenfolge der Anzeige: erst Identitaet, dann Technik, dann Werk. */
const ORDER = [
  'make',
  'model',
  'series',
  'trim',
  'model_year',
  'manufacturer',
  'vehicle_type',
  'body_class',
  'fuel_type',
  'engine_model',
  'engine_displacement_l',
  'engine_cylinders',
  'engine_power_kw',
  'drive_type',
  'transmission',
  'doors',
  'seats',
  'country',
  'region',
  'plant_company',
  'plant_city',
  'plant_country',
  'plant_code'
];

const HIDDEN = new Set(['country_code']);

function sourceLabel(source: string): string {
  // 'vindb:wmi:nhtsa_vpic' -> 'vindb / nhtsa_vpic'
  const parts = source.split(':');
  return parts.length > 1 ? `${parts[0]} / ${parts[parts.length - 1]}` : source;
}

export default function FieldTable({
  fields,
  locale
}: {
  fields: Record<string, FieldResult>;
  locale: string;
}) {
  const t = useTranslations('result');
  const attributes = useTranslations('attributes');

  const keys = [
    ...ORDER.filter((key) => fields[key] && !HIDDEN.has(key)),
    ...Object.keys(fields).filter((key) => !ORDER.includes(key) && !HIDDEN.has(key))
  ];

  if (keys.length === 0) return null;

  return (
    <div className="overflow-hidden rounded-xl border" style={{borderColor: 'var(--border)'}}>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs" style={{color: 'var(--muted)'}}>
            <th className="px-4 py-2.5 font-medium">{t('field')}</th>
            <th className="px-4 py-2.5 font-medium">{t('value')}</th>
            <th className="hidden px-4 py-2.5 font-medium sm:table-cell">{t('sourcesColumn')}</th>
            <th className="px-4 py-2.5 text-right font-medium">{t('confidenceColumn')}</th>
          </tr>
        </thead>
        <tbody>
          {keys.map((key) => {
            const field = fields[key];
            const translated = field.value_i18n?.[locale];
            return (
              <tr key={key} className="border-t align-top" style={{borderColor: 'var(--border)'}}>
                <td className="px-4 py-3" style={{color: 'var(--muted)'}}>
                  {attributes.has(key) ? attributes(key) : key}
                </td>
                <td className="px-4 py-3 font-medium">
                  {translated ?? String(field.value)}
                  {field.conflict ? (
                    <div className="mt-1 text-xs" style={{color: 'var(--warn)'}}>
                      {t('conflict')}
                      {field.alternatives.length > 0 ? (
                        <span style={{color: 'var(--muted)'}}>
                          {' '}
                          · {t('alternatives')}:{' '}
                          {field.alternatives.map((alt) => String(alt.value)).join(', ')}
                        </span>
                      ) : null}
                    </div>
                  ) : null}
                </td>
                <td
                  className="hidden px-4 py-3 font-mono text-xs sm:table-cell"
                  style={{color: 'var(--muted)'}}
                >
                  {field.sources.map(sourceLabel).join(', ')}
                </td>
                <td className="px-4 py-3">
                  <div className="flex justify-end">
                    <ConfidenceBar value={field.confidence} compact />
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
