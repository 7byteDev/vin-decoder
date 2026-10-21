import {useTranslations} from 'next-intl';

import type {VehicleDetail} from '@/lib/types';

/**
 * Eckdaten des Fahrzeugs - die linke Spalte der Detailansicht.
 *
 * Das Markenlogo stammt aus Wikimedia Commons (ueber die Wikidata-
 * Eigenschaft P154 der Marke). Fehlt es - etwa bei Aufbauherstellern -,
 * tritt ein Monogramm aus dem Markennamen an seine Stelle.
 */

/** "e1*70/156-2007/37*0430" -> "DE" (Land, das die Genehmigung erteilt hat). */
const EU_APPROVAL_COUNTRIES: Record<string, string> = {
  e1: 'DE', e2: 'FR', e3: 'IT', e4: 'NL', e5: 'SE', e6: 'BE', e7: 'HU',
  e8: 'CZ', e9: 'ES', e11: 'GB', e12: 'AT', e13: 'LU', e17: 'FI', e18: 'DK',
  e19: 'RO', e20: 'PL', e21: 'PT', e23: 'GR', e24: 'IE', e25: 'HR',
  e26: 'SI', e27: 'SK', e29: 'EE', e32: 'LV', e34: 'BG', e36: 'LT',
  e49: 'CY', e50: 'MT'
};

function approvalCountry(number: string | null): string | null {
  if (!number) return null;
  const match = /^e(\d{1,2})/i.exec(number.trim());
  return match ? (EU_APPROVAL_COUNTRIES[`e${match[1]}`] ?? null) : null;
}

/** Länderkürzel als Plakette - robuster als Flaggen-Emoji, die nicht überall rendern. */
function CountryChip({code, tone = 'primary'}: {code: string; tone?: 'primary' | 'neutral'}) {
  const styles =
    tone === 'primary'
      ? {background: 'var(--primary)', color: 'var(--on-primary)'}
      : {background: 'var(--surface-2)', color: 'var(--text-soft)'};
  return (
    <span
      className="inline-flex items-center rounded px-1.5 py-0.5 font-mono text-[11px] font-bold tracking-wide"
      style={styles}
    >
      {code}
    </span>
  );
}

function Row({
  icon,
  label,
  children
}: {
  icon: React.ReactNode;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-start gap-2.5 py-1.5">
      <span className="mt-0.5 shrink-0" style={{color: 'var(--muted)'}} aria-hidden>
        {icon}
      </span>
      <span className="text-xs uppercase tracking-wide" style={{color: 'var(--muted)'}}>
        {label}:
      </span>
      <span className="ml-auto text-right text-sm font-medium">{children}</span>
    </div>
  );
}

const ICONS = {
  vin: (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <rect x="1.5" y="3.5" width="13" height="9" rx="1.5" />
      <path d="M4 7h3M4 9.5h5" strokeLinecap="round" />
    </svg>
  ),
  year: (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <rect x="2" y="3" width="12" height="11" rx="1.5" />
      <path d="M2 6.5h12M5.5 1.5v3M10.5 1.5v3" strokeLinecap="round" />
    </svg>
  ),
  approval: (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M8 1.5 2.5 3.8v4c0 3 2.3 5.6 5.5 6.7 3.2-1.1 5.5-3.7 5.5-6.7v-4L8 1.5Z" />
      <path d="m5.8 7.8 1.6 1.6 3-3.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  source: (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <circle cx="8" cy="8" r="6.3" />
      <path d="M1.7 8h12.6M8 1.7c1.7 1.8 2.6 4 2.6 6.3S9.7 12.5 8 14.3C6.3 12.5 5.4 10.3 5.4 8S6.3 3.5 8 1.7Z" />
    </svg>
  )
} as const;

export default function VehicleIdentity({
  vehicle,
  vin
}: {
  vehicle: VehicleDetail;
  vin: string;
}) {
  const t = useTranslations('detail');
  const name = [vehicle.make, vehicle.model].filter(Boolean).join(' ');
  const monogram = (vehicle.make ?? '?').replace(/[^A-Za-zÀ-ž]/g, '').slice(0, 2).toUpperCase();
  const productionYear = vehicle.approval_date?.slice(0, 4);
  const euCountry = approvalCountry(vehicle.eu_approval_number);

  return (
    <section
      className="rounded-xl border p-5"
      style={{borderColor: 'var(--border)', background: 'var(--surface)'}}
    >
      <div className="flex items-center gap-3">
        {vehicle.logo ? (
          <span
            className="flex h-11 w-11 shrink-0 items-center justify-center overflow-hidden rounded-full p-1.5"
            style={{background: 'var(--surface-2)'}}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={vehicle.logo.url}
              alt={vehicle.make ?? ''}
              className="max-h-full max-w-full object-contain"
              loading="lazy"
            />
          </span>
        ) : (
          <span
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-sm font-bold"
            style={{background: 'var(--primary-soft)', color: 'var(--primary)'}}
            aria-hidden
          >
            {monogram}
          </span>
        )}
        <h1 className="text-xl font-semibold leading-tight">{name}</h1>
      </div>

      <div className="mt-4 divide-y" style={{borderColor: 'var(--border)'}}>
        <Row icon={ICONS.vin} label={t('searchedVin')}>
          <span className="font-mono">{vin.toUpperCase()}</span>
        </Row>

        {vehicle.vin_patterns.length > 0 ? (
          <Row icon={ICONS.vin} label={t('basePattern')}>
            <span className="font-mono">{vehicle.vin_patterns[0]}</span>
          </Row>
        ) : null}

        {productionYear ? (
          <Row icon={ICONS.year} label={t('productionYear')}>
            {productionYear}
          </Row>
        ) : null}

        {vehicle.eu_approval_number ? (
          <Row icon={ICONS.approval} label={t('euApproval')}>
            <span className="flex items-center justify-end gap-2">
              <span className="font-mono text-xs">{vehicle.eu_approval_number}</span>
              {euCountry ? <CountryChip code={euCountry} tone="neutral" /> : null}
            </span>
          </Row>
        ) : null}

        {vehicle.approval_number ? (
          <Row icon={ICONS.approval} label={t('approvalNumber')}>
            <span className="flex items-center justify-end gap-2">
              <span className="font-mono">{vehicle.approval_number}</span>
              <CountryChip code="CH" tone="neutral" />
            </span>
          </Row>
        ) : null}

        <Row icon={ICONS.source} label={t('source')}>
          <span className="flex items-center justify-end gap-2">
            <CountryChip code="EU" />
            <span className="text-xs" style={{color: 'var(--muted)'}}>
              ASTRA TARGA
            </span>
          </span>
        </Row>
      </div>
    </section>
  );
}
