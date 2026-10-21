import {getMessages, getTranslations, unstable_setRequestLocale} from 'next-intl/server';
import Link from 'next/link';
import {notFound} from 'next/navigation';

import Breadcrumb from '@/components/Breadcrumb';
import {catalogName} from '@/lib/catalogNames';
import {
  fetchBrandModels,
  fetchBrands,
  fetchGenerationVehicles,
  fetchModelGenerations
} from '@/lib/server-api';

type Props = {
  params: {locale: string; brand: string; model: string; generation: string};
};

// Der Bestand aendert sich durch Importe; fuenf Minuten halten die
// Seite frisch, ohne bei jedem Aufruf die API zu belasten.
export const revalidate = 300;

export async function generateMetadata({params}: Props) {
  const brands = (await fetchBrands()) ?? [];
  const brand = brands.find((b) => b.slug === params.brand);
  const models = (await fetchBrandModels(params.brand)) ?? [];
  const model = models.find((m) => m.slug === params.model);
  return {
    title: [brand?.name, model?.model, params.generation.toUpperCase()]
      .filter(Boolean)
      .join(' ')
  };
}

/**
 * Fahrzeuge einer Baureihe.
 *
 * Technisch gleiche Typengenehmigungen stehen in einer Zeile: ueber die
 * Haelfte des Bestands ist doppelt gefuehrt, und der Unterschied liegt
 * allein in der Genehmigungsnummer. Wie viele es waren, steht daneben.
 */
export default async function GenerationPage({
  params: {locale, brand, model, generation}
}: Props) {
  unstable_setRequestLocale(locale);
  const t = await getTranslations({locale, namespace: 'browse'});
  const nav = await getTranslations({locale, namespace: 'nav'});
  const units = await getTranslations({locale, namespace: 'units'});
  // Die Wertetabelle wird direkt gelesen: nicht jeder Rohwert des ASTRA
  // hat eine Uebersetzung, und ein fehlender Schluessel soll den Rohwert
  // zeigen statt einen Fehler zu werfen.
  const messages = (await getMessages({locale})) as {
    values?: Record<string, Record<string, string>>;
  };

  const brands = (await fetchBrands()) ?? [];
  const info = brands.find((b) => b.slug === brand);
  const models = (await fetchBrandModels(brand)) ?? [];
  const currentModel = models.find((m) => m.slug === model);
  const generations = (await fetchModelGenerations(brand, model)) ?? [];
  const currentGen = generations.find((g) => g.slug === generation);
  if (!info || !currentModel || !currentGen) notFound();

  const vehicles = (await fetchGenerationVehicles(brand, model, generation)) ?? [];
  const label = (group: string, raw: string | null) =>
    raw ? (messages.values?.[group]?.[raw] ?? raw) : '–';

  return (
    <div className="space-y-6">
      <Breadcrumb
        items={[
          {label: nav('home'), href: `/${locale}`},
          {label: nav('brands'), href: `/${locale}/brands`},
          {label: info.name, href: `/${locale}/brands/${brand}`},
          {label: catalogName(currentModel.model, locale), href: `/${locale}/brands/${brand}/${model}`},
          {label: catalogName(currentGen.platform, locale)}
        ]}
      />

      <div className="grid items-start gap-5 lg:grid-cols-[2fr_1fr]">
        <div>
          <h1 className="text-2xl font-semibold">
            {info.name} {catalogName(currentGen.platform, locale)}
          </h1>
          <p className="text-sm" style={{color: 'var(--muted)'}}>
            {t('years')}: {currentGen.year_from} – {currentGen.year_to} ·{' '}
            {currentGen.vehicles.toLocaleString(locale)} {t('vehicles')}
          </p>
        </div>
        {currentGen.thumb_url ? (
          <span
            className="hidden overflow-hidden rounded-xl border lg:block"
            style={{borderColor: 'var(--border)'}}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={currentGen.thumb_url} alt="" className="w-full object-cover" />
          </span>
        ) : null}
      </div>

      {vehicles.length === 0 ? (
        <p style={{color: 'var(--muted)'}}>{t('empty')}</p>
      ) : (
        <div
          className="scroll-x overflow-hidden rounded-xl border"
          style={{borderColor: 'var(--border)', background: 'var(--surface)'}}
        >
          <table className="w-full min-w-[38rem] text-sm">
            <thead>
              <tr
                className="border-b text-left text-xs uppercase tracking-wide"
                style={{borderColor: 'var(--border)', color: 'var(--muted)'}}
              >
                <th className="px-4 py-2.5 font-medium">{t('vehicle')}</th>
                <th className="px-4 py-2.5 font-medium">{t('fuel')}</th>
                <th className="px-4 py-2.5 font-medium">{t('power')}</th>
                <th className="px-4 py-2.5 font-medium">{t('transmission')}</th>
                <th className="px-4 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {vehicles.map((vehicle) => (
                <tr
                  key={vehicle.id}
                  className="border-b last:border-0"
                  style={{borderColor: 'var(--border)'}}
                >
                  <td className="px-4 py-2.5">
                    <span className="font-medium">{vehicle.model}</span>
                    {vehicle.displacement_ccm ? (
                      <span className="ml-2 text-xs" style={{color: 'var(--muted)'}}>
                        {vehicle.displacement_ccm} {units('ccm')}
                      </span>
                    ) : null}
                    {vehicle.approvals > 1 ? (
                      <span
                        className="ml-2 rounded px-1.5 py-0.5 text-[10px]"
                        style={{background: 'var(--surface-2)', color: 'var(--muted)'}}
                        title={vehicle.approval_numbers.join(', ')}
                      >
                        {vehicle.approvals} {t('approvals')} · {t('sameData')}
                      </span>
                    ) : null}
                  </td>
                  <td className="px-4 py-2.5">{label('fuel', vehicle.fuel_type)}</td>
                  <td className="px-4 py-2.5">
                    {vehicle.power_kw ? (
                      <>
                        {vehicle.power_ps} {units('ps')}
                        <span className="ml-1 text-xs" style={{color: 'var(--muted)'}}>
                          ({vehicle.power_kw} {units('kw')})
                        </span>
                      </>
                    ) : (
                      '–'
                    )}
                  </td>
                  <td className="px-4 py-2.5">
                    {label('transmission', vehicle.transmission)}
                    {vehicle.gears ? (
                      <span className="ml-1 text-xs" style={{color: 'var(--muted)'}}>
                        {units('gears', {count: vehicle.gears})}
                      </span>
                    ) : null}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <Link
                      href={`/${locale}/vehicle/${vehicle.id}`}
                      className="whitespace-nowrap rounded-md border px-2.5 py-1 text-xs font-medium"
                      style={{borderColor: 'var(--border)', color: 'var(--primary)'}}
                    >
                      {t('open')} →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
