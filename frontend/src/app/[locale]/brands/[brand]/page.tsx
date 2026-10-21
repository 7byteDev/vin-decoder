import {getTranslations, unstable_setRequestLocale} from 'next-intl/server';
import Link from 'next/link';
import {notFound} from 'next/navigation';

import Breadcrumb from '@/components/Breadcrumb';
import {catalogName} from '@/lib/catalogNames';
import {fetchBrandModels, fetchBrands} from '@/lib/server-api';

type Props = {params: {locale: string; brand: string}};

// Der Bestand aendert sich durch Importe; fuenf Minuten halten die
// Seite frisch, ohne bei jedem Aufruf die API zu belasten.
export const revalidate = 300;

async function brandName(slug: string) {
  const brands = (await fetchBrands()) ?? [];
  return brands.find((b) => b.slug === slug) ?? null;
}

export async function generateMetadata({params}: Props) {
  const brand = await brandName(params.brand);
  return {title: brand ? brand.name : params.brand};
}

/** Modelle einer Marke, nach Bestand sortiert. */
export default async function BrandPage({params: {locale, brand}}: Props) {
  unstable_setRequestLocale(locale);
  const t = await getTranslations({locale, namespace: 'browse'});
  const nav = await getTranslations({locale, namespace: 'nav'});

  const info = await brandName(brand);
  if (!info) notFound();
  const models = (await fetchBrandModels(brand)) ?? [];

  return (
    <div className="space-y-6">
      <Breadcrumb
        items={[
          {label: nav('home'), href: `/${locale}`},
          {label: nav('brands'), href: `/${locale}/brands`},
          {label: info.name}
        ]}
      />

      <div className="flex items-center gap-3">
        {info.logo_url ? (
          <span
            className="flex h-12 w-12 items-center justify-center overflow-hidden rounded-full p-1.5"
            style={{background: 'var(--surface-2)'}}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={info.logo_url} alt="" className="max-h-full max-w-full object-contain" />
          </span>
        ) : null}
        <div>
          <h1 className="text-2xl font-semibold">{info.name}</h1>
          <p className="text-sm" style={{color: 'var(--muted)'}}>
            {models.length} {t('models')} · {info.vehicles.toLocaleString(locale)}{' '}
            {t('vehicles')}
          </p>
        </div>
      </div>

      {models.length === 0 ? (
        <p style={{color: 'var(--muted)'}}>{t('empty')}</p>
      ) : (
        <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {models.map((model) => (
            <li key={model.slug}>
              <Link
                href={`/${locale}/brands/${brand}/${model.slug}`}
                className="flex h-full flex-col overflow-hidden rounded-xl border transition-shadow hover:shadow-md"
                style={{borderColor: 'var(--border)', background: 'var(--surface)'}}
              >
                <span
                  className="flex aspect-[16/9] items-center justify-center overflow-hidden"
                  style={{background: 'var(--surface-2)'}}
                >
                  {model.thumb_url ? (
                    /* eslint-disable-next-line @next/next/no-img-element */
                    <img
                      src={model.thumb_url}
                      alt=""
                      className="h-full w-full object-cover"
                      loading="lazy"
                    />
                  ) : (
                    <span className="text-xs" style={{color: 'var(--muted)'}}>
                      {catalogName(model.model, locale)}
                    </span>
                  )}
                </span>
                <span className="flex items-end justify-between gap-3 px-4 py-3">
                  <span>
                    <span className="block text-sm font-medium">
                      {catalogName(model.model, locale)}
                    </span>
                    <span className="text-xs" style={{color: 'var(--muted)'}}>
                      {model.generations} {t('generations')} · {model.year_from}–
                      {model.year_to}
                    </span>
                  </span>
                  <span className="shrink-0 text-xs" style={{color: 'var(--muted)'}}>
                    {model.vehicles.toLocaleString(locale)}
                  </span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
