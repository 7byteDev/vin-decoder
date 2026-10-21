import createMiddleware from 'next-intl/middleware';

import {defaultLocale, locales} from './i18n';

export default createMiddleware({
  locales,
  defaultLocale,
  localePrefix: 'always',
  // Ohne dies wuerde der Accept-Language-Header des Browsers entscheiden -
  // ein deutscher Browser landete dann auf /de statt auf der gewuenschten
  // Standardsprache. Der Sprachumschalter bleibt davon unberuehrt.
  localeDetection: false
});

export const config = {
  // Alles ausser statischen Dateien und API-Routen
  matcher: ['/((?!api|_next|_vercel|.*\..*).*)']
};
