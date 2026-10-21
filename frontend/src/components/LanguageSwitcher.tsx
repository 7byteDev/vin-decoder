'use client';

import {usePathname, useRouter} from 'next/navigation';
import {useTranslations} from 'next-intl';
import {useTransition} from 'react';

import {locales} from '@/i18n';

const LABELS: Record<string, string> = {en: 'EN', de: 'DE', tr: 'TR'};

export default function LanguageSwitcher({current}: {current: string}) {
  const t = useTranslations('nav');
  const pathname = usePathname();
  const router = useRouter();
  const [pending, startTransition] = useTransition();

  function switchTo(locale: string) {
    const rest = pathname.replace(new RegExp(`^/(${locales.join('|')})`), '') || '/';
    startTransition(() => router.replace(`/${locale}${rest}`));
  }

  return (
    <nav aria-label={t('language')} className="flex shrink-0 gap-1 text-xs">
      {locales.map((locale) => {
        const active = locale === current;
        return (
          <button
            key={locale}
            type="button"
            onClick={() => switchTo(locale)}
            disabled={pending || active}
            aria-current={active ? 'true' : undefined}
            className="rounded-md border px-2.5 py-1.5 font-medium transition-colors disabled:cursor-default"
            style={{
              borderColor: active ? 'var(--accent)' : 'var(--border)',
              background: active ? 'var(--accent-soft)' : 'var(--surface)',
              color: active ? 'var(--accent)' : 'var(--muted)'
            }}
          >
            {LABELS[locale]}
          </button>
        );
      })}
    </nav>
  );
}
