import createNextIntlPlugin from 'next-intl/plugin';

const withNextIntl = createNextIntlPlugin('./src/i18n.ts');

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  /**
   * Die API liegt in einem eigenen Container. Bilder aus der eigenen
   * Ablage werden mit relativer Adresse ausgeliefert (/api/v1/image/..),
   * damit der Browser nicht die interne Portnummer kennen muss - dieser
   * Umschreibung leitet sie weiter.
   */
  async rewrites() {
    const target = (
      process.env.API_INTERNAL_URL ??
      process.env.NEXT_PUBLIC_API_BASE_URL ??
      'http://localhost:8000'
    ).replace(/\/$/, '');
    return [{source: '/api/v1/:path*', destination: `${target}/api/v1/:path*`}];
  }
};

export default withNextIntl(nextConfig);
