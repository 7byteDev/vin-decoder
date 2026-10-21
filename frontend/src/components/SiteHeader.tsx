import Link from 'next/link';
import {getTranslations} from 'next-intl/server';

import LanguageSwitcher from '@/components/LanguageSwitcher';

/**
 * Kopfzeile mit Marke, Hauptnavigation und Sprachumschalter.
 * Auf jeder Seite sichtbar, damit der Weg zurück immer einen Klick weit ist.
 */
export default async function SiteHeader({locale}: {locale: string}) {
  const nav = await getTranslations({locale, namespace: 'nav'});
  const meta = await getTranslations({locale, namespace: 'meta'});

  const links = [
    {href: `/${locale}`, label: nav('home')},
    {href: `/${locale}/brands`, label: nav('brands')},
    {href: `/${locale}#vin`, label: nav('whatIsVin')},
    {href: `/${locale}#approval`, label: nav('typeApproval')},
    {href: `/${locale}#sources`, label: nav('sources')}
  ];

  return (
    <header
      className="sticky top-0 z-20 border-b backdrop-blur"
      style={{borderColor: 'var(--border)', background: 'color-mix(in srgb, var(--surface) 88%, transparent)'}}
    >
      <div className="mx-auto flex max-w-5xl items-center gap-4 px-5 py-3">
        <Link href={`/${locale}`} className="flex shrink-0 items-center gap-2.5">
          <span
            className="flex h-8 w-8 items-center justify-center rounded-lg font-mono text-xs font-bold"
            style={{background: 'var(--primary)', color: 'var(--on-primary)'}}
            aria-hidden
          >
            VIN
          </span>
          <span className="hidden text-sm font-semibold sm:inline">{meta('title')}</span>
        </Link>

        <nav className="scroll-x ml-auto flex items-center gap-1" aria-label={nav('menu')}>
          {links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="whitespace-nowrap rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors hover:opacity-80"
              style={{color: 'var(--text-soft)'}}
            >
              {link.label}
            </Link>
          ))}
        </nav>

        <div className="shrink-0">
          <LanguageSwitcher current={locale} />
        </div>
      </div>
    </header>
  );
}
