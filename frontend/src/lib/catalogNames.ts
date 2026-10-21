/**
 * Modell- und Baureihennamen des Katalogs sprachgerecht schreiben.
 *
 * Der Katalog ist deutsch: "1er-Reihe", "E-Klasse", "3-Tuerer". Der
 * Eigenname bleibt (eine 1er ist auch auf Tuerkisch eine 1), aber die
 * Gattungsbezeichnung dahinter gehoert uebersetzt - sonst steht im
 * tuerkischen Menue mitten im Satz ein deutsches Wort.
 *
 * Uebersetzt wird nur, was eine feste Entsprechung hat. Phantasienamen
 * ("Gran Tourer", "Cabrio") bleiben unangetastet.
 */

type Rule = {pattern: RegExp; replace: Record<string, string>};

const RULES: Rule[] = [
  // "1er-Reihe" -> "1 Serisi" / "1 Series"
  {
    pattern: /(\d+)er[-\s]?Reihe/gi,
    replace: {tr: '$1 Serisi', en: '$1 Series', de: '$1er-Reihe'}
  },
  // "E-Klasse" -> "E-Serisi" / "E-Class"
  {
    pattern: /([A-Za-zÄÖÜ]{1,4})[-\s]Klasse/g,
    replace: {tr: '$1 Serisi', en: '$1-Class', de: '$1-Klasse'}
  },
  // "3-Tuerer" -> "3 kapili" / "3-door"
  {
    pattern: /(\d+)[-\s]?T(?:ü|ue)rer/gi,
    replace: {tr: '$1 kapılı', en: '$1-door', de: '$1-Türer'}
  },
  // "(1. Facelift)" -> "(1. makyaj)" / "(1st facelift)"
  {
    pattern: /\((\d+)\.\s*Facelift\)/gi,
    replace: {tr: '($1. makyaj)', en: '($1. facelift)', de: '($1. Facelift)'}
  },
  // "1. Generation" -> "1. Nesil" / "1st generation"
  {
    pattern: /(\d+)\.\s*Generation/gi,
    replace: {tr: '$1. Nesil', en: '$1. generation', de: '$1. Generation'}
  },
  // "Kombi" ist im Tuerkischen gelaeufig, im Englischen nicht
  {
    pattern: /\bKombi\b/g,
    replace: {tr: 'Station Wagon', en: 'Estate', de: 'Kombi'}
  }
];

/** Katalogname in der Sprache der Oberflaeche. */
export function catalogName(name: string, locale: string): string {
  const lang = ['tr', 'en', 'de'].includes(locale) ? locale : 'de';
  let out = name ?? '';
  for (const rule of RULES) {
    const replacement = rule.replace[lang];
    if (replacement) out = out.replace(rule.pattern, replacement);
  }
  return out;
}
