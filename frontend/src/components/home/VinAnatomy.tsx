import {useTranslations} from 'next-intl';

/** Beispiel-VIN eines SEAT Ibiza - dieselbe, die auch die Suche vorschlägt. */
const SEGMENTS = [
  {key: 'wmi', text: 'VSS', range: '1–3', color: 'var(--primary)', soft: 'var(--primary-soft)'},
  {key: 'vds', text: 'ZZZ6J', range: '4–8', color: 'var(--accent)', soft: 'var(--accent-soft)'},
  {key: 'check', text: 'Z', range: '9', color: 'var(--muted)', soft: 'var(--surface-2)'},
  {key: 'year', text: 'E', range: '10', color: 'var(--good)', soft: 'var(--good-soft)'},
  {key: 'plant', text: 'R', range: '11', color: 'var(--primary)', soft: 'var(--primary-soft)'},
  {key: 'serial', text: '058590', range: '12–17', color: 'var(--muted)', soft: 'var(--surface-2)'}
] as const;

/** Zerlegt eine Beispiel-VIN und erklärt jeden Abschnitt. */
export default function VinAnatomy() {
  const t = useTranslations('home.anatomy');

  return (
    <section
      className="rounded-xl border p-5 sm:p-6"
      style={{borderColor: 'var(--border)', background: 'var(--surface)'}}
    >
      <h2 className="mb-4 text-base font-semibold">{t('title')}</h2>

      <div className="scroll-x pb-2">
        <div className="flex min-w-max items-stretch gap-1">
          {SEGMENTS.map((segment) => (
            <div key={segment.key} className="flex flex-col items-center">
              <span
                className="rounded-t-md px-2 pb-0.5 pt-1 text-[10px] font-medium uppercase tracking-wide"
                style={{color: segment.color}}
              >
                {t('positions', {range: segment.range})}
              </span>
              <span
                className="rounded-md border-2 px-2.5 py-2 font-mono text-lg tracking-[0.18em]"
                style={{borderColor: segment.color, background: segment.soft, color: 'var(--text)'}}
              >
                {segment.text}
              </span>
            </div>
          ))}
        </div>
      </div>

      <dl className="mt-5 grid gap-x-6 gap-y-3 sm:grid-cols-2">
        {SEGMENTS.map((segment) => (
          <div key={segment.key} className="flex gap-3">
            <span
              className="mt-1 h-2 w-2 shrink-0 rounded-full"
              style={{background: segment.color}}
              aria-hidden
            />
            <div>
              <dt className="text-sm font-medium">{t(segment.key)}</dt>
              <dd className="text-xs leading-relaxed" style={{color: 'var(--muted)'}}>
                {t(`${segment.key}Text`)}
              </dd>
            </div>
          </div>
        ))}
      </dl>
    </section>
  );
}
