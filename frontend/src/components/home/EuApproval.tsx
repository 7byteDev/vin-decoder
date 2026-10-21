import {useTranslations} from 'next-intl';

/** Die vier Teile einer EG-Typgenehmigungsnummer. */
const NUMBER_PARTS = [
  {text: 'e1', key: 'part1', color: 'var(--primary)'},
  {text: '2007/46', key: 'part2', color: 'var(--accent)'},
  {text: '2064', key: 'part3', color: 'var(--good)'},
  {text: '07', key: 'part4', color: 'var(--muted)'}
] as const;

function Check({children}: {children: React.ReactNode}) {
  return (
    <li className="flex gap-2.5">
      <span className="mt-0.5 shrink-0 font-semibold" style={{color: 'var(--good)'}} aria-hidden>
        &#10003;
      </span>
      <span className="text-sm leading-relaxed" style={{color: 'var(--text-soft)'}}>
        {children}
      </span>
    </li>
  );
}

/** Erklärt die EU-Typgenehmigung - die Grundlage unserer Technikdaten. */
export default function EuApproval() {
  const t = useTranslations('home.eu');

  return (
    <section
      className="rounded-xl border p-5 sm:p-6"
      style={{borderColor: 'var(--border)', background: 'var(--surface)'}}
    >
      <h2 className="text-base font-semibold">{t('title')}</h2>
      <p className="mt-2 text-sm leading-relaxed" style={{color: 'var(--text-soft)'}}>
        {t('body')}
      </p>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <div>
          <h3 className="mb-2.5 text-sm font-semibold">{t('findTitle')}</h3>
          <ul className="space-y-2">
            <Check>{t('find1')}</Check>
            <Check>{t('find2')}</Check>
            <Check>{t('find3')}</Check>
          </ul>
        </div>

        <div>
          <h3 className="mb-2.5 text-sm font-semibold">{t('numberTitle')}</h3>
          <div className="scroll-x pb-1">
            <div className="flex min-w-max items-center gap-0.5 font-mono text-base">
              {NUMBER_PARTS.map((part, index) => (
                <span key={part.key} className="flex items-center gap-0.5">
                  {index > 0 ? <span style={{color: 'var(--muted)'}}>*</span> : null}
                  <span
                    className="rounded-md px-2 py-1 font-semibold"
                    style={{background: 'var(--surface-2)', color: part.color}}
                  >
                    {part.text}
                  </span>
                </span>
              ))}
            </div>
          </div>
          <dl className="mt-3 space-y-1.5">
            {NUMBER_PARTS.map((part) => (
              <div key={part.key} className="flex gap-2.5 text-xs">
                <dt
                  className="w-16 shrink-0 font-mono font-semibold"
                  style={{color: part.color}}
                >
                  {part.text}
                </dt>
                <dd style={{color: 'var(--muted)'}}>{t(part.key)}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>

      <div className="mt-6 border-t pt-5" style={{borderColor: 'var(--border)'}}>
        <h3 className="mb-2.5 text-sm font-semibold">{t('whyTitle')}</h3>
        <ul className="grid gap-2 sm:grid-cols-3">
          <Check>{t('why1')}</Check>
          <Check>{t('why2')}</Check>
          <Check>{t('why3')}</Check>
        </ul>
      </div>
    </section>
  );
}
