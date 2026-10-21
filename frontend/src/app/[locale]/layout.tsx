import type {Metadata} from 'next';
import {NextIntlClientProvider} from 'next-intl';
import {getMessages, getTranslations, unstable_setRequestLocale} from 'next-intl/server';
import {notFound} from 'next/navigation';

import SiteHeader from '@/components/SiteHeader';
import {locales, type Locale} from '@/i18n';

import '../globals.css';

type Props = {
  children: React.ReactNode;
  params: {locale: string};
};

export function generateStaticParams() {
  return locales.map((locale) => ({locale}));
}

export async function generateMetadata({params: {locale}}: Props): Promise<Metadata> {
  const t = await getTranslations({locale, namespace: 'meta'});
  return {
    title: t('title'),
    description: t('description')
  };
}

export default async function LocaleLayout({children, params: {locale}}: Props) {
  if (!locales.includes(locale as Locale)) notFound();
  unstable_setRequestLocale(locale);

  const messages = await getMessages();

  return (
    <html lang={locale}>
      <body className="min-h-screen font-sans">
        <NextIntlClientProvider messages={messages}>
          <SiteHeader locale={locale} />
          <div className="mx-auto flex min-h-screen max-w-5xl flex-col px-5 py-6 sm:py-9">

            <main className="flex-1">{children}</main>
          </div>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
