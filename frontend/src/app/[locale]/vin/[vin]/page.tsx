import type {Metadata} from 'next';
import Link from 'next/link';
import {getTranslations, unstable_setRequestLocale} from 'next-intl/server';

import Breadcrumb from '@/components/Breadcrumb';
import MatchTable from '@/components/MatchTable';
import StructurePanel from '@/components/StructurePanel';
import VinSearchForm from '@/components/VinSearchForm';
import {decodeVinOnServer} from '@/lib/server-api';

type Props = {params: {locale: string; vin: string}};

export async function generateMetadata({params}: Props): Promise<Metadata> {
  const vin = params.vin.toUpperCase();
  const t = await getTranslations({locale: params.locale, namespace: 'meta'});
  return {
    title: `${vin} – ${t('title')}`,
    description: t('description'),
    robots: {index: true, follow: true}
  };
}

export default async function VinResultsPage({params}: Props) {
  const {locale} = params;
  unstable_setRequestLocale(locale);

  const vin = params.vin.toUpperCase();
  const list = await getTranslations({locale, namespace: 'list'});
  const nav = await getTranslations({locale, namespace: 'nav'});
  const errors = await getTranslations({locale, namespace: 'errors'});
  const result = await decodeVinOnServer(vin, locale);

  const crumbs = [{label: nav('home'), href: `/${locale}`}, {label: vin}];

  if (!result) {
    return (
      <div className="space-y-6">
        <Breadcrumb items={crumbs} />
        <VinSearchForm initialVin={vin} />
        <p
          className="rounded-xl border p-4 text-sm"
          style={{borderColor: 'var(--danger)', color: 'var(--danger)'}}
        >
          {errors('network')}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <Breadcrumb items={crumbs} />
      <VinSearchForm initialVin={vin} />

      <section>
        <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-base font-semibold">
            {result.match_count > 0
              ? list('count', {count: result.match_count})
              : list('title')}
          </h2>
          <Link
            href={`/${locale}`}
            className="text-xs underline underline-offset-2"
            style={{color: 'var(--muted)'}}
          >
            {list('back')}
          </Link>
        </div>

        {result.match_count > 0 ? (
          <>
            <p className="mb-4 text-xs" style={{color: 'var(--muted)'}}>
              {list('hint')}
            </p>
            <MatchTable matches={result.matches} vin={vin} locale={locale} />
          </>
        ) : (
          <div
            className="rounded-xl border p-5 text-sm"
            style={{borderColor: 'var(--border)', background: 'var(--surface)'}}
          >
            <p className="font-medium">{list('none')}</p>
            <p className="mt-1 text-xs" style={{color: 'var(--muted)'}}>
              {list('noneHint')}
            </p>
          </div>
        )}
      </section>

      <StructurePanel structure={result.structure} vinMasked={result.vin_masked} />
    </div>
  );
}
