import {notFound} from 'next/navigation';
import {getRequestConfig} from 'next-intl/server';

export const locales = ['tr', 'de', 'en'] as const;
export type Locale = (typeof locales)[number];
// Standardsprache: Tuerkisch. Ohne Sprachpraefix leitet die Middleware hierhin.
export const defaultLocale: Locale = 'tr';

export default getRequestConfig(async ({locale}) => {
  if (!locales.includes(locale as Locale)) notFound();

  return {
    messages: (await import(`../messages/${locale}.json`)).default
  };
});
