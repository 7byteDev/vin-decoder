import Link from 'next/link';

export type Crumb = {label: string; href?: string};

/**
 * Brotkrumen-Navigation in eigener Leiste.
 *
 * Zusaetzlich als strukturierte Daten ausgezeichnet (schema.org
 * BreadcrumbList) - Suchmaschinen zeigen den Pfad dann direkt im Treffer,
 * was bei einer Seite je VIN den Unterschied macht.
 */
export default function Breadcrumb({items}: {items: Crumb[]}) {
  if (items.length === 0) return null;

  const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: items.map((item, index) => ({
      '@type': 'ListItem',
      position: index + 1,
      name: item.label,
      ...(item.href ? {item: item.href} : {})
    }))
  };

  return (
    <>
      <nav
        aria-label="Breadcrumb"
        className="scroll-x rounded-lg border px-3.5 py-2"
        style={{borderColor: 'var(--border)', background: 'var(--surface-2)'}}
      >
        <ol className="flex min-w-max items-center gap-1.5 text-xs" style={{color: 'var(--muted)'}}>
          {items.map((item, index) => {
            const last = index === items.length - 1;
            return (
              <li key={`${item.label}-${index}`} className="flex items-center gap-1.5">
                {index > 0 ? (
                  <span aria-hidden style={{opacity: 0.5}}>
                    ›
                  </span>
                ) : null}
                {item.href && !last ? (
                  <Link
                    href={item.href}
                    className="underline-offset-2 hover:underline"
                    style={{color: 'var(--primary)'}}
                  >
                    {item.label}
                  </Link>
                ) : (
                  <span
                    className={last ? 'font-medium' : undefined}
                    style={last ? {color: 'var(--text-soft)'} : undefined}
                    aria-current={last ? 'page' : undefined}
                  >
                    {item.label}
                  </span>
                )}
              </li>
            );
          })}
        </ol>
      </nav>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{__html: JSON.stringify(jsonLd)}}
      />
    </>
  );
}
