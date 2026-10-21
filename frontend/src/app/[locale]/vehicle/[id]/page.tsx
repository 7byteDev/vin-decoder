import {getTranslations, unstable_setRequestLocale} from 'next-intl/server';
import {notFound} from 'next/navigation';

import Breadcrumb from '@/components/Breadcrumb';
import ConsumptionEmissions from '@/components/ConsumptionEmissions';
import SpecSections from '@/components/SpecSections';
import VehicleGallery from '@/components/VehicleGallery';
import VehicleHighlights from '@/components/VehicleHighlights';
import VehicleIdentity from '@/components/VehicleIdentity';
import {fetchVehicle} from '@/lib/server-api';

type Props = {params: {locale: string; id: string}};

// Der Bestand aendert sich durch Importe; fuenf Minuten halten die
// Seite frisch, ohne bei jedem Aufruf die API zu belasten.
export const revalidate = 300;

export async function generateMetadata({params}: Props) {
  const vehicle = await fetchVehicle(params.id);
  if (!vehicle) return {};
  const name = [vehicle.make, vehicle.model].filter(Boolean).join(' ');
  return {
    title: name,
    description: [
      name,
      vehicle.displacement_ccm ? `${vehicle.displacement_ccm} cm³` : null,
      vehicle.power_kw ? `${vehicle.power_kw} kW` : null,
      vehicle.fuel_type
    ]
      .filter(Boolean)
      .join(' · ')
  };
}

/**
 * Dieselbe Detailansicht wie unter /vin/..., nur ohne konkrete FIN.
 *
 * Wer ueber die Marken blaettert, hat keine FIN - die Ausfuehrung laesst
 * sich dann nicht bestimmen, weshalb Masse und Gewichte hier als Spanne
 * stehen bleiben. Sonst ist die Seite identisch.
 */
export default async function VehiclePage({params: {locale, id}}: Props) {
  unstable_setRequestLocale(locale);

  const vehicle = await fetchVehicle(id);
  if (!vehicle) notFound();

  const t = await getTranslations({locale, namespace: 'detail'});
  const nav = await getTranslations({locale, namespace: 'nav'});
  const name = [vehicle.make, vehicle.model].filter(Boolean).join(' ');

  return (
    <div className="space-y-6">
      <Breadcrumb
        items={[
          {label: nav('home'), href: `/${locale}`},
          {label: nav('brands'), href: `/${locale}/brands`},
          {label: name || nav('vehicle')}
        ]}
      />

      <div className="grid items-stretch gap-5 lg:grid-cols-2">
        <VehicleIdentity vehicle={vehicle} vin={vehicle.vin_patterns[0] ?? ''} />
        <VehicleGallery images={vehicle.images} title={name} />
      </div>

      <VehicleHighlights vehicle={vehicle} />
      <ConsumptionEmissions
        consumption={vehicle.consumption}
        emissions={vehicle.emissions}
      />
      <SpecSections sections={vehicle.sections} />

      {vehicle.attribution ? (
        <p className="text-xs" style={{color: 'var(--muted)'}}>
          {t('source')}: {vehicle.attribution}
        </p>
      ) : null}
    </div>
  );
}
