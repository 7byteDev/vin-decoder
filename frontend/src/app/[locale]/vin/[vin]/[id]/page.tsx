import type {Metadata} from 'next';
import Link from 'next/link';
import {notFound} from 'next/navigation';
import {getTranslations, unstable_setRequestLocale} from 'next-intl/server';

import Breadcrumb from '@/components/Breadcrumb';
import ConsumptionEmissions from '@/components/ConsumptionEmissions';
import SpecSections from '@/components/SpecSections';
import VehicleGallery from '@/components/VehicleGallery';
import VehicleHighlights from '@/components/VehicleHighlights';
import VehicleIdentity from '@/components/VehicleIdentity';
import {fetchVehicle} from '@/lib/server-api';

type Props = {params: {locale: string; vin: string; id: string}};

export async function generateMetadata({params}: Props): Promise<Metadata> {
  const vehicle = await fetchVehicle(params.id, params.vin);
  if (!vehicle) return {title: params.vin.toUpperCase()};
  const name = [vehicle.make, vehicle.model].filter(Boolean).join(' ');
  return {
    title: `${name} – ${params.vin.toUpperCase()}`,
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

export default async function VehicleDetailPage({params}: Props) {
  const {locale, vin, id} = params;
  unstable_setRequestLocale(locale);

  const vehicle = await fetchVehicle(id, vin);
  if (!vehicle) notFound();

  const t = await getTranslations({locale, namespace: 'detail'});
  const nav = await getTranslations({locale, namespace: 'nav'});
  const name = [vehicle.make, vehicle.model].filter(Boolean).join(' ');

  return (
    <div className="space-y-6">
      <Breadcrumb
        items={[
          {label: nav('home'), href: `/${locale}`},
          {label: vin.toUpperCase(), href: `/${locale}/vin/${vin}`},
          {label: name || nav('vehicle')}
        ]}
      />

      <Link
        href={`/${locale}/vin/${vin}`}
        className="inline-flex items-center gap-1.5 text-xs underline-offset-2 hover:underline"
        style={{color: 'var(--primary)'}}
      >
        <span aria-hidden>‹</span> {t('back')}
      </Link>

      {/* Kopfbereich zweispaltig: links die Eckdaten, rechts die Galerie.
          Auf schmalen Geraeten stapeln sich beide. */}
      <div className="grid items-stretch gap-5 lg:grid-cols-2">
        <VehicleIdentity vehicle={vehicle} vin={vin} />
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
