import {getTranslations, unstable_setRequestLocale} from 'next-intl/server';
import Link from 'next/link';
import {notFound} from 'next/navigation';

import Breadcrumb from '@/components/Breadcrumb';
import {catalogName} from '@/lib/catalogNames';
import {fetchBrandModels, fetchBrands, fetchModelGenerations} from '@/lib/server-api';

type Props = {params: {locale: string; brand: string; model: string}};

// Der Bestand aendert sich durch Importe; fuenf Minuten halten die
// Seite frisch, ohne bei jedem Aufruf die API zu belasten.
export const revalidate = 300;

export async function generateMetadata({params}: Props) {
  const brands = (await fetchBrands()) ?? [];
  const brand = brands.find((b) => b.slug === params.brand);
  const models = (await fetchBrandModels(params.brand)) ?? [];
  const model = models.find((m) => m.slug === params.model);
  return {title: [brand?.name, model?.model].filter(Boolean).join(' ') || params.model};
}

/**
 * Baureihen eines Modells - je Generation eine Kachel mit Bauzeitraum,
 * Fahrzeugzahl und einem Foto der Generation.
 */
export default async function ModelPage({params: {locale, brand, model}}: Props) {
  unstable_setRequestLocale(locale);
  const t = await getTranslations({locale, namespace: 'browse'});
  const nav = await getTranslations({locale, namespace: 'nav'});

  const brands = (await fetchBrands()) ?? [];
  const info = brands.find((b) => b.slug === brand);
  const models = (await fetchBrandModels(brand)) ?? [];
  const current = models.find((m) => m.slug === model);
  if (!info || !current) notFound();

  const generations = (await fetchModelGenerations(brand, model)) ?? [];

  return (
    <div className="space-y-6">
      <Breadcrumb
        items={[
          {label: nav('home'), href: `/${locale}`},
          {label: nav('brands'), href: `/${locale}/brands`},
          {label: info.name, href: `/${locale}/brands/${brand}`},
          {label: catalogName(current.model, locale)}
        ]}
      />

      <div>
        <h1 className="text-2xl font-semibold">
          {info.name} {catalogName(current.model, locale)}
        </h1>
        <p className="text-sm" style={{color: 'var(--muted)'}}>
          {generations.length} {t('generations')} ·{' '}
          {current.vehicles.toLocaleString(locale)} {t('vehicles')}
        </p>
      </div>

      {generations.length === 0 ? (
        <p style={{color: 'var(--muted)'}}>{t('empty')}</p>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {generations.map((generation) => (
            <li key={generation.slug}>
              <Link
                href={`/${locale}/brands/${brand}/${model}/${generation.slug}`}
                className="flex h-full flex-col overflow-hidden rounded-xl border transition-shadow hover:shadow-md"
                style={{borderColor: 'var(--border)', background: 'var(--surface)'}}
              >
                <span
                  className="flex aspect-[16/9] items-center justify-center overflow-hidden"
                  style={{background: 'var(--surface-2)'}}
                >
                  {generation.thumb_url ? (
                    /* eslint-disable-next-line @next/next/no-img-element */
                    <img
                      src={generation.thumb_url}
                      alt=""
                      className="h-full w-full object-cover"
                      loading="lazy"
                    />
                  ) : (
                    <span className="text-xs" style={{color: 'var(--muted)'}}>
                      {catalogName(generation.platform, locale)}
                    </span>
                  )}
                </span>
                <span className="flex flex-col gap-0.5 px-4 py-3">
                  <span className="text-sm font-medium">
                    {catalogName(generation.platform, locale)}
                  </span>
                  <span className="text-xs" style={{color: 'var(--muted)'}}>
                    {t('years')}: {generation.year_from} – {generation.year_to} ·{' '}
                    {generation.vehicles.toLocaleString(locale)} {t('vehicles')}
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
