import {getTranslations, unstable_setRequestLocale} from 'next-intl/server';
import Link from 'next/link';

import Breadcrumb from '@/components/Breadcrumb';
import BrandSort, {type SortKey} from '@/components/BrandSort';
import {fetchBrands} from '@/lib/server-api';

type Props = {params: {locale: string}; searchParams: {sort?: string}};

// Der Bestand aendert sich durch Importe; fuenf Minuten halten die
// Seite frisch, ohne bei jedem Aufruf die API zu belasten.
export const revalidate = 300;

export async function generateMetadata({params}: Props) {
  const t = await getTranslations({locale: params.locale, namespace: 'browse'});
  return {title: t('title'), description: t('intro')};
}

/** Markenkuerzel als Ersatz, solange kein Logo vorliegt. */
function Monogram({name}: {name: string}) {
  const letters = name.replace(/[^A-Za-zÀ-ž]/g, '').slice(0, 2).toUpperCase();
  return (
    <span
      className="flex h-12 w-12 items-center justify-center rounded-full text-sm font-bold"
      style={{background: 'var(--primary-soft)', color: 'var(--primary)'}}
      aria-hidden
    >
      {letters}
    </span>
  );
}

/**
 * Einstieg ohne FIN: alle Marken des Bestands als Kachelraster.
 *
 * Sortiert nach Fahrzeugzahl - wer hier landet, sucht in aller Regel eine
 * der grossen Marken, nicht einen Aufbauhersteller mit drei Eintraegen.
 */
export default async function BrandsPage({params: {locale}, searchParams}: Props) {
  unstable_setRequestLocale(locale);
  const t = await getTranslations({locale, namespace: 'browse'});
  const nav = await getTranslations({locale, namespace: 'nav'});
  const all = (await fetchBrands()) ?? [];

  // Wie im Autokatalog: Name oder Bestand, je auf- oder absteigend.
  // Die API liefert bereits nach Bestand absteigend.
  const keys: SortKey[] = ['count-desc', 'count-asc', 'name-asc', 'name-desc'];
  const sort: SortKey = keys.includes(searchParams.sort as SortKey)
    ? (searchParams.sort as SortKey)
    : 'count-desc';
  const byName = (a: (typeof all)[number], b: (typeof all)[number]) =>
    a.name.localeCompare(b.name, locale);
  const brands =
    sort === 'count-desc'
      ? all
      : sort === 'count-asc'
        ? [...all].reverse()
        : sort === 'name-asc'
          ? [...all].sort(byName)
          : [...all].sort((a, b) => byName(b, a));

  return (
    <div className="space-y-6">
      <Breadcrumb
        items={[{label: nav('home'), href: `/${locale}`}, {label: nav('brands')}]}
      />

      <div>
        <h1 className="text-2xl font-semibold">{t('title')}</h1>
        <p className="mt-1 max-w-2xl text-sm" style={{color: 'var(--muted)'}}>
          {t('intro')}
        </p>
      </div>

      <BrandSort
        locale={locale}
        current={sort}
        label={t('sort')}
        options={[
          {key: 'count-desc', text: t('sortCountDesc')},
          {key: 'count-asc', text: t('sortCountAsc')},
          {key: 'name-asc', text: t('sortNameAsc')},
          {key: 'name-desc', text: t('sortNameDesc')}
        ]}
      />

      {brands.length === 0 ? (
        <p style={{color: 'var(--muted)'}}>{t('empty')}</p>
      ) : (
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {brands.map((brand) => (
            <li key={brand.slug}>
              <Link
                href={`/${locale}/brands/${brand.slug}`}
                className="flex h-full flex-col items-center gap-2 rounded-xl border p-4 text-center transition-shadow hover:shadow-md"
                style={{borderColor: 'var(--border)', background: 'var(--surface)'}}
              >
                {brand.logo_url ? (
                  <span className="flex h-12 items-center justify-center">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={brand.logo_url}
                      alt=""
                      className="max-h-12 max-w-[7rem] object-contain"
                      loading="lazy"
                    />
                  </span>
                ) : (
                  <Monogram name={brand.name} />
                )}
                <span className="text-sm font-medium">{brand.name}</span>
                <span className="text-xs" style={{color: 'var(--muted)'}}>
                  {brand.models} {t('models')} · {brand.vehicles.toLocaleString(locale)}{' '}
                  {t('vehicles')}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
