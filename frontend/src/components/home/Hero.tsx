import {useTranslations} from 'next-intl';

import VinSearchForm from '@/components/VinSearchForm';

function Badge({children}: {children: React.ReactNode}) {
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium backdrop-blur"
      style={{background: 'rgba(255,255,255,0.14)', color: '#fff'}}
    >
      {children}
    </span>
  );
}

/** Kopfbereich der Startseite: Suche plus die drei Kernaussagen. */
export default function Hero() {
  const t = useTranslations('home.hero');

  return (
    <section
      className="rounded-2xl px-6 py-10 sm:px-10 sm:py-14"
      style={{
        background:
          'linear-gradient(135deg, var(--hero-from) 0%, var(--hero-via) 55%, var(--hero-to) 100%)',
        boxShadow: 'var(--shadow-lg)'
      }}
    >
      <h1 className="max-w-2xl text-2xl font-semibold leading-tight text-white sm:text-3xl">
        {t('title')}
      </h1>
      <p className="mt-3 max-w-2xl text-sm leading-relaxed" style={{color: 'rgba(255,255,255,0.82)'}}>
        {t('subtitle')}
      </p>

      <div className="mt-7 rounded-xl p-4 sm:p-5" style={{background: 'var(--surface)'}}>
        <VinSearchForm />
      </div>

      <div className="mt-5 flex flex-wrap gap-2">
        <Badge>
          <span aria-hidden>&#10003;</span> {t('badgeOfficial')}
        </Badge>
        <Badge>
          <span aria-hidden>&#8635;</span> {t('badgeUpdated')}
        </Badge>
        <Badge>
          <span aria-hidden>&#9679;</span> {t('badgePrivacy')}
        </Badge>
      </div>
    </section>
  );
}
