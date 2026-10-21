import {useTranslations} from 'next-intl';

/**
 * Zeigt den ISO-3779-Aufbau der VIN. Der Seriennummernblock ist bereits
 * serverseitig maskiert - hier kommt nie eine vollstaendige VIN an.
 *
 * Farbgebung und Abstaende folgen der Erklaerbox der Startseite, damit
 * derselbe Abschnitt auf beiden Seiten dieselbe Farbe hat.
 */
export default function VinSegments({vinMasked}: {vinMasked: string}) {
  const t = useTranslations('structure');
  const segments = [
    {
      key: 'wmi',
      text: vinMasked.slice(0, 3),
      label: t('wmi'),
      range: '1–3',
      color: 'var(--primary)',
      soft: 'var(--primary-soft)'
    },
    {
      key: 'vds',
      text: vinMasked.slice(3, 9),
      label: t('vds'),
      range: '4–9',
      color: 'var(--accent)',
      soft: 'var(--accent-soft)'
    },
    {
      key: 'vis',
      text: vinMasked.slice(9),
      label: t('vis'),
      range: '10–17',
      color: 'var(--good)',
      soft: 'var(--good-soft)'
    }
  ];

  return (
    <div className="scroll-x pb-1">
      <div className="flex min-w-max items-stretch gap-4">
        {segments.map((segment) => (
          <div key={segment.key} className="flex flex-col items-start gap-1">
            <span
              className="text-[10px] font-medium uppercase tracking-wide"
              style={{color: segment.color}}
            >
              {segment.label}
              <span className="ml-1 font-mono opacity-70">{segment.range}</span>
            </span>
            <span
              className="rounded-md border-2 px-2.5 py-2 font-mono text-base tracking-[0.18em]"
              style={{borderColor: segment.color, background: segment.soft, color: 'var(--text)'}}
            >
              {segment.text}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
