import {useTranslations} from 'next-intl';

import type {VehicleDetail} from '@/lib/types';

type Entry = {
  label: string;
  value: string;
  tone?: 'good' | 'warn' | 'unknown';
  note?: string;
};

/**
 * Ab diesem Radstand gilt ein Fahrzeug hier als lang - die Grenze kommt
 * aus der Praxis (Stellplatz- und Garagenmasse), nicht aus dem Datensatz.
 */
const WHEELBASE_LIMIT_MM = 3200;

/** Hinterlegung einer hervorgehobenen Zeile. */
const TONES = {
  plain: {borderColor: 'transparent', background: 'transparent'},
  good: {borderColor: 'var(--good)', background: 'var(--good-soft)'},
  warn: {borderColor: 'var(--danger)', background: 'var(--danger-soft)'},
  unknown: {borderColor: 'var(--accent)', background: 'var(--accent-soft)'}
} as const;

/**
 * Farbe der Radstand-Zeile.
 *
 * Gruen oder rot nur, wenn die Grenze eindeutig auf einer Seite liegt.
 * Deckt die Genehmigung beide Ausfuehrungen ab und die VIN legt sich
 * nicht fest, waere jede der beiden Farben eine Behauptung - dann bleibt
 * es beim dritten Zustand.
 */
function wheelbaseTone(lower: number, upper: number): 'good' | 'warn' | 'unknown' {
  if (upper < WHEELBASE_LIMIT_MM) return 'good';
  if (lower >= WHEELBASE_LIMIT_MM) return 'warn';
  return 'unknown';
}

/**
 * Die wichtigsten Werte auf einen Blick, bevor die vollstaendigen
 * Abschnitte der Typengenehmigung folgen.
 */
export default function VehicleHighlights({vehicle}: {vehicle: VehicleDetail}) {
  const t = useTranslations('detail');
  const attributes = useTranslations('attributes');
  const units = useTranslations('units');
  const values = useTranslations('values');

  const label = (group: string, raw: string | null) => {
    if (!raw) return null;
    const key = `${group}.${raw}`;
    return values.has(key) ? values(key) : raw;
  };

  /**
   * Eine Typengenehmigung deckt mehrere Varianten ab, deshalb fuehrt das
   * ASTRA Abmessungen und Gewichte als Spanne. Wo es eine gibt, wird sie
   * gezeigt - ein einzelner Wert taeuschte Genauigkeit vor.
   */
  const span = (field: string, value: number, unit: string) => {
    const upper = vehicle.ranges?.[field];
    return upper ? `${value} – ${upper} ${unit}` : `${value} ${unit}`;
  };

  const groups: {title: string; entries: Entry[]}[] = [
    {
      title: t('engine'),
      entries: [
        vehicle.power_kw && {
          label: attributes('engine_power_kw'),
          value: `${vehicle.power_ps} ${units('ps')} (${vehicle.power_kw} ${units('kw')})`
        },
        vehicle.displacement_ccm && {
          label: attributes('engine_displacement_l'),
          value: `${vehicle.displacement_ccm} ${units('ccm')}`
        },
        vehicle.fuel_type && {
          label: attributes('fuel_type'),
          value: label('fuel', vehicle.fuel_type) as string
        },
        vehicle.engine_code && {
          label: attributes('engine_model'),
          value: vehicle.engine_code
        },
        vehicle.torque_nm && {
          label: attributes('torque'),
          value: `${vehicle.torque_nm} ${units('nm')}${
            vehicle.torque_rpm ? ` @ ${vehicle.torque_rpm} ${units('rpm')}` : ''
          }`
        },
        vehicle.transmission && {
          label: attributes('transmission'),
          value: `${label('transmission', vehicle.transmission)}${
            vehicle.gears ? `, ${units('gears', {count: vehicle.gears})}` : ''
          }`
        },
        vehicle.drive_type && {
          label: attributes('drive_type'),
          value: label('drive', vehicle.drive_type) as string
        }
      ].filter(Boolean) as Entry[]
    },
    {
      title: t('dimensions'),
      entries: [
        vehicle.length_mm && {
          label: attributes('length'),
          value: span('length_mm', vehicle.length_mm, units('mm'))
        },
        vehicle.width_mm && {
          label: attributes('width'),
          value: span('width_mm', vehicle.width_mm, units('mm'))
        },
        vehicle.height_mm && {
          label: attributes('height'),
          value: span('height_mm', vehicle.height_mm, units('mm'))
        },
        vehicle.wheelbase_mm && {
          label: attributes('wheelbase'),
          value: span('wheelbase_mm', vehicle.wheelbase_mm, units('mm')),
          tone: wheelbaseTone(
            vehicle.wheelbase_mm,
            vehicle.ranges?.wheelbase_mm ?? vehicle.wheelbase_mm
          ),
          // Nur der Zweifelsfall wird beschriftet. Ist der Wert eindeutig,
          // spricht die Zahl fuer sich.
          note: vehicle.ranges?.wheelbase_mm ? t('wheelbaseUncertain') : undefined
        },
        vehicle.weight_kg && {
          label: attributes('weight'),
          value: span('weight_kg', vehicle.weight_kg, units('kg'))
        },
        vehicle.max_weight_kg && {
          label: attributes('max_weight'),
          value: span('max_weight_kg', vehicle.max_weight_kg, units('kg'))
        },
        vehicle.top_speed_kmh && {
          label: attributes('top_speed'),
          value: `${vehicle.top_speed_kmh} ${units('kmh')}`
        }
      ].filter(Boolean) as Entry[]
    },
    {
      title: t('general'),
      entries: [
        vehicle.body_form && {label: attributes('body_class'), value: vehicle.body_form},
        vehicle.doors && {label: attributes('doors'), value: String(vehicle.doors)},
        vehicle.seats_total && {
          label: attributes('seats'),
          value: span('seats_total', vehicle.seats_total, '').trim()
        },
        vehicle.vehicle_class && {
          label: attributes('vehicle_class'),
          value: vehicle.vehicle_class
        },
        vehicle.vehicle_kind && {label: attributes('vehicle_type'), value: vehicle.vehicle_kind},
        vehicle.manufacturer && {
          label: attributes('manufacturer'),
          value: vehicle.manufacturer
        }
      ].filter(Boolean) as Entry[]
    }
  ].filter((group) => group.entries.length > 0);

  return (
    <div className="grid gap-4 sm:grid-cols-3">
      {groups.map((group) => (
        <section
          key={group.title}
          className="rounded-xl border p-4"
          style={{borderColor: 'var(--border)', background: 'var(--surface)'}}
        >
          <h2 className="mb-2 text-sm font-semibold">{group.title}</h2>
          <dl className="space-y-1.5 text-sm">
            {group.entries.map((entry) => (
              <div
                key={entry.label}
                // Rahmen und Polsterung tragen ALLE Zeilen, sonst ruecken
                // Beschriftung und Wert der hervorgehobenen Zeile aus der
                // Flucht. Nur die Farbe unterscheidet sie.
                className="flex justify-between gap-3 rounded-md border px-2 py-1"
                style={entry.tone ? TONES[entry.tone] : TONES.plain}
              >
                <dt className="text-xs" style={{color: 'var(--muted)'}}>
                  {entry.label}
                </dt>
                <dd className="text-right font-medium">
                  {entry.value}
                  {entry.note ? (
                    <span
                      className="mt-0.5 block text-[10px] font-normal leading-tight"
                      style={{color: 'var(--muted)'}}
                    >
                      {entry.note}
                    </span>
                  ) : null}
                </dd>
              </div>
            ))}
          </dl>
        </section>
      ))}
    </div>
  );
}
