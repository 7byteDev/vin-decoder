'use client';

import {useTranslations} from 'next-intl';
import {useCallback, useEffect, useState} from 'react';

import type {VehicleImage} from '@/lib/types';

/**
 * Fotogalerie aus Wikimedia Commons, mit Lightbox.
 *
 * Die Bilder sind frei lizenziert (CC BY, CC BY-SA, gemeinfrei) und werden
 * direkt von Wikimedia ausgeliefert. Beide Lizenzfamilien verlangen die
 * Namensnennung: sie steht in der vergroesserten Ansicht am Bild und
 * verlinkt auf Lizenz und Dateiseite. In der Kachel bleibt sie weg, damit
 * die Galerie dieselbe Hoehe hat wie die Eckdaten daneben.
 */

function Credit({image, light}: {image: VehicleImage; light?: boolean}) {
  const color = light ? 'rgba(255,255,255,0.72)' : 'var(--muted)';
  return (
    <p className="text-xs" style={{color}}>
      {image.author ? <span>{image.author}</span> : null}
      {image.author && image.license ? ' · ' : null}
      {image.license ? (
        image.license_url ? (
          <a
            href={image.license_url}
            target="_blank"
            rel="noreferrer"
            className="underline underline-offset-2"
            style={{color}}
          >
            {image.license}
          </a>
        ) : (
          <span>{image.license}</span>
        )
      ) : null}
      {image.page_url ? (
        <>
          {' · '}
          <a
            href={image.page_url}
            target="_blank"
            rel="noreferrer"
            className="underline underline-offset-2"
            style={{color}}
          >
            Wikimedia Commons
          </a>
        </>
      ) : null}
    </p>
  );
}

export default function VehicleGallery({
  images,
  title
}: {
  images: VehicleImage[];
  title: string;
}) {
  const t = useTranslations('detail');
  const [active, setActive] = useState(0);
  const [zoomed, setZoomed] = useState(false);

  const count = images.length;
  const step = useCallback(
    (delta: number) => setActive((index) => (index + delta + count) % count),
    [count]
  );

  // Tastatur nur bedienen, solange die Lightbox offen ist
  useEffect(() => {
    if (!zoomed) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') setZoomed(false);
      if (event.key === 'ArrowRight') step(1);
      if (event.key === 'ArrowLeft') step(-1);
    }
    document.addEventListener('keydown', onKey);
    // Hintergrund nicht mitscrollen lassen
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = previous;
    };
  }, [zoomed, step]);

  if (count === 0) return null;
  const current = images[Math.min(active, count - 1)];

  return (
    <>
      <section
        className="relative flex h-full min-h-[19rem] flex-col overflow-hidden rounded-xl border"
        style={{borderColor: 'var(--border)', background: 'var(--surface)'}}
      >
        <button
          type="button"
          onClick={() => setZoomed(true)}
          aria-label={t('enlarge')}
          className="group relative flex w-full flex-1 items-center justify-center overflow-hidden"
          style={{background: 'var(--surface-2)'}}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={current.url}
            alt={current.description ?? title}
            className="absolute inset-0 h-full w-full object-contain transition-transform duration-200 group-hover:scale-[1.02]"
            loading="eager"
          />
          <span
            className="absolute bottom-3 right-3 rounded-full px-2.5 py-1 text-xs font-medium opacity-0 transition-opacity group-hover:opacity-100"
            style={{background: 'rgba(0,0,0,0.6)', color: '#fff'}}
          >
            {t('enlarge')}
          </span>
          {count > 1 ? (
            <span
              className="absolute right-3 top-3 rounded-full px-2.5 py-1 text-xs font-medium"
              style={{background: 'rgba(0,0,0,0.55)', color: '#fff'}}
            >
              {active + 1} / {count}
            </span>
          ) : null}
        </button>

        {count > 1 ? (
          <div
            className="scroll-x absolute inset-x-0 bottom-0 px-3 py-2.5"
            style={{
              background: 'linear-gradient(to top, rgba(8,14,22,0.72), rgba(8,14,22,0))'
            }}
          >
            <div className="flex gap-2">
              {images.map((image, index) => (
                <button
                  key={image.file_key}
                  type="button"
                  onClick={() => setActive(index)}
                  aria-label={`${index + 1}`}
                  aria-current={index === active}
                  className="h-12 w-16 shrink-0 overflow-hidden rounded-md border-2 transition-opacity"
                  style={{
                    borderColor: index === active ? '#fff' : 'rgba(255,255,255,0.35)',
                    opacity: index === active ? 1 : 0.65
                  }}
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={image.thumb_url}
                    alt=""
                    className="h-full w-full object-cover"
                    loading="lazy"
                  />
                </button>
              ))}
            </div>
          </div>
        ) : null}

      </section>

      {zoomed ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={title}
          className="fixed inset-0 z-50 flex flex-col items-center justify-center p-4 sm:p-8"
          style={{background: 'rgba(8, 14, 22, 0.88)', backdropFilter: 'blur(2px)'}}
          onClick={() => setZoomed(false)}
        >
          <button
            type="button"
            onClick={() => setZoomed(false)}
            aria-label={t('close')}
            className="absolute right-4 top-4 flex h-10 w-10 items-center justify-center rounded-full text-2xl leading-none"
            style={{background: 'rgba(255,255,255,0.12)', color: '#fff'}}
          >
            ×
          </button>

          {count > 1 ? (
            <>
              <button
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  step(-1);
                }}
                aria-label={t('previous')}
                className="absolute left-2 top-1/2 flex h-11 w-11 -translate-y-1/2 items-center justify-center rounded-full text-2xl sm:left-6"
                style={{background: 'rgba(255,255,255,0.12)', color: '#fff'}}
              >
                ‹
              </button>
              <button
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  step(1);
                }}
                aria-label={t('next')}
                className="absolute right-2 top-1/2 flex h-11 w-11 -translate-y-1/2 items-center justify-center rounded-full text-2xl sm:right-6"
                style={{background: 'rgba(255,255,255,0.12)', color: '#fff'}}
              >
                ›
              </button>
            </>
          ) : null}

          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={current.url}
            alt={current.description ?? title}
            className="max-h-[78vh] max-w-full rounded-lg object-contain"
            onClick={(event) => event.stopPropagation()}
          />

          <div
            className="mt-3 max-w-2xl text-center"
            onClick={(event) => event.stopPropagation()}
          >
            <p className="text-sm font-medium text-white">{title}</p>
            <div className="mt-1">
              <Credit image={current} light />
            </div>
            <p className="mt-1 text-xs italic" style={{color: 'rgba(255,255,255,0.55)'}}>
              {t('imageNote')}
            </p>
            {count > 1 ? (
              <p className="mt-1 text-xs" style={{color: 'rgba(255,255,255,0.55)'}}>
                {active + 1} / {count}
              </p>
            ) : null}
          </div>
        </div>
      ) : null}
    </>
  );
}
