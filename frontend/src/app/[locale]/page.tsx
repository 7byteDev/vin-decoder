import {getTranslations, unstable_setRequestLocale} from 'next-intl/server';

import Breadcrumb from '@/components/Breadcrumb';
import EuApproval from '@/components/home/EuApproval';
import Hero from '@/components/home/Hero';
import RecentSearches from '@/components/home/RecentSearches';
import {CountryTable, ModelYearTable} from '@/components/home/ReferenceTables';
import VinAnatomy from '@/components/home/VinAnatomy';
import {apiDocsUrl} from '@/lib/api';
import {fetchCountryRanges, fetchModelYears} from '@/lib/server-api';

type Props = {params: {locale: string}};

function Card({title, children}: {title: string; children: React.ReactNode}) {
  return (
    <section
      className="rounded-xl border p-5"
      style={{borderColor: 'var(--border)', background: 'var(--surface)'}}
    >
      <h2 className="text-sm font-semibold">{title}</h2>
      <div className="mt-2 text-xs leading-relaxed" style={{color: 'var(--muted)'}}>
        {children}
      </div>
    </section>
  );
}

export default async function HomePage({params: {locale}}: Props) {
  unstable_setRequestLocale(locale);

  const home = await getTranslations({locale, namespace: 'home'});
  const privacy = await getTranslations({locale, namespace: 'privacy'});
  const sources = await getTranslations({locale, namespace: 'sources'});
  const footer = await getTranslations({locale, namespace: 'footer'});

  const nav = await getTranslations({locale, namespace: 'nav'});
  const [modelYears, countries] = await Promise.all([fetchModelYears(), fetchCountryRanges()]);

  return (
    <div className="space-y-10">
      <Breadcrumb items={[{label: nav('home')}]} />

      <Hero />

      <RecentSearches locale={locale} />

      <section
        id="vin"
        className="scroll-mt-20 rounded-xl border p-5 sm:p-6"
        style={{borderColor: 'var(--border)', background: 'var(--surface)'}}
      >
        <h2 className="text-base font-semibold">{home('vin.title')}</h2>
        <p className="mt-2 text-sm leading-relaxed" style={{color: 'var(--text-soft)'}}>
          {home('vin.body1')}
        </p>
        <p className="mt-3 text-sm leading-relaxed" style={{color: 'var(--text-soft)'}}>
          {home('vin.body2')}
        </p>
        <div
          className="mt-4 rounded-lg border-l-4 py-2.5 pl-4 pr-3"
          style={{borderColor: 'var(--primary)', background: 'var(--primary-soft)'}}
        >
          <div className="text-xs font-semibold" style={{color: 'var(--primary)'}}>
            {home('vin.whereTitle')}
          </div>
          <p className="mt-1 text-xs leading-relaxed" style={{color: 'var(--text-soft)'}}>
            {home('vin.where')}
          </p>
        </div>
      </section>

      <VinAnatomy />

      <div className="grid gap-4 sm:grid-cols-3">
        <Card title={home('facts.lengthTitle')}>{home('facts.length')}</Card>
        <Card title={home('facts.lettersTitle')}>{home('facts.letters')}</Card>
        <Card title={home('facts.sourceTitle')}>{home('facts.source')}</Card>
      </div>

      <section
        className="rounded-xl border-l-4 p-5"
        style={{borderColor: 'var(--accent)', background: 'var(--accent-soft)'}}
      >
        <h2 className="text-sm font-semibold" style={{color: 'var(--accent)'}}>
          {home('legacy.title')}
        </h2>
        <p className="mt-1.5 text-sm leading-relaxed" style={{color: 'var(--text-soft)'}}>
          {home('legacy.body')}
        </p>
      </section>

      {modelYears ? <ModelYearTable codes={modelYears} /> : null}
      {countries ? <CountryTable ranges={countries} /> : null}

      <div id="approval" className="scroll-mt-20">
        <EuApproval />
      </div>

      <div id="sources" className="grid scroll-mt-20 gap-4 sm:grid-cols-2">
        <Card title={sources('title')}>
          <p>{sources('note')}</p>
          <ul className="mt-2.5 space-y-1">
            <li>{sources('structural')}</li>
            <li>{sources('vindb')}</li>
            <li>{sources('nhtsa_vpic')}</li>
            <li>{sources('vininfo')}</li>
          </ul>
        </Card>
        <Card title={privacy('title')}>{privacy('body')}</Card>
      </div>

      <footer
        className="flex flex-wrap items-center justify-between gap-2 border-t pt-5 text-xs"
        style={{borderColor: 'var(--border)', color: 'var(--muted)'}}
      >
        <span>{footer('madeFor')}</span>
        <a href={apiDocsUrl} className="underline underline-offset-2">
          {footer('api')}
        </a>
      </footer>
    </div>
  );
}
