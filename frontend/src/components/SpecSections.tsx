'use client';

import {useLocale, useTranslations} from 'next-intl';
import {useState} from 'react';

import {specLabel, specValue} from '@/lib/specLabels';
import type {SpecSection} from '@/lib/types';

/**
 * Der vollstaendige Datensatz der Typengenehmigung, gegliedert wie das
 * ASTRA ihn fuehrt. Abschnittstitel und Feldnamen sind uebersetzt; die
 * Werte stammen unveraendert aus dem amtlichen Datensatz - dort steht
 * deutschsprachiger Klartext (etwa "im Motorraum, rechts"), der sich
 * nicht sinnvoll maschinell uebersetzen laesst.
 */
export default function SpecSections({sections}: {sections: SpecSection[]}) {
  const t = useTranslations('sections');
  const locale = useLocale();
  const [open, setOpen] = useState<string | null>(sections[0]?.key ?? null);

  if (sections.length === 0) return null;

  return (
    <div className="space-y-2">
      {sections.map((section) => {
        const expanded = open === section.key;
        const title = t.has(section.key) ? t(section.key) : section.label;
        const entries = Object.entries(section.entries);
        return (
          <section
            key={`${section.key}-${section.label}`}
            className="overflow-hidden rounded-xl border"
            style={{borderColor: 'var(--border)', background: 'var(--surface)'}}
          >
            <button
              type="button"
              onClick={() => setOpen(expanded ? null : section.key)}
              aria-expanded={expanded}
              className="flex w-full items-center justify-between gap-3 px-5 py-3 text-left"
            >
              <span className="text-sm font-semibold">{title}</span>
              <span className="flex items-center gap-2 text-xs" style={{color: 'var(--muted)'}}>
                {entries.length}
                <span aria-hidden>{expanded ? '−' : '+'}</span>
              </span>
            </button>
            {expanded ? (
              <dl className="border-t px-5 py-3" style={{borderColor: 'var(--border)'}}>
                {entries.map(([key, value]) => (
                  <div
                    key={key}
                    className="flex flex-col gap-0.5 border-b py-2 last:border-0 sm:flex-row sm:justify-between sm:gap-6"
                    style={{borderColor: 'var(--border)'}}
                  >
                    <dt className="text-xs" style={{color: 'var(--muted)'}}>
                      {specLabel(key, locale)}
                    </dt>
                    <dd className="text-sm sm:max-w-[60%] sm:text-right">
                      {specValue(key, value, locale)}
                    </dd>
                  </div>
                ))}
              </dl>
            ) : null}
          </section>
        );
      })}
    </div>
  );
}
