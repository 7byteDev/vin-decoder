/**
 * Uebersetzung der Feldnamen aus dem amtlichen TARGA-Datensatz.
 *
 * Das ASTRA liefert die Feldnamen ausschliesslich auf Deutsch und nach
 * einem festen Muster: eine zweistellige Positionsnummer, der Begriff,
 * dahinter Zusaetze fuer Wertebereich ("von"/"bis"), Getriebeart
 * ("mech"/"autom") und laufende Nummern ("Z1", "Getriebe 2"). Statt alle
 * 171 Kombinationen einzeln zu pflegen, wird der Name zerlegt und nur der
 * Begriff uebersetzt - die Zusaetze kommen aus einer zweiten Tabelle.
 *
 * Die Positionsnummer bleibt stehen: sie ist die amtliche Nummerierung
 * des Typenscheins und erlaubt den Abgleich mit dem Originaldokument.
 *
 * Die Tabelle liegt bewusst hier und nicht in ``messages/*.json``: die
 * Schluessel enthalten Punkte und Schraegstriche ("Md. max Nm",
 * "Drehschemellenk./ABS"), die next-intl als Namensraum-Trenner deutet.
 */

type Dict = Record<string, string>;

/** Begriffe, die nur als Ganzes sinnvoll sind (keine Zerlegung). */
const WHOLE: Record<string, Dict> = {
  de: {
    'gültig für Importdatum bis': 'Gültig für Importdatum bis',
    'Erweiterung TG vom': 'Erweiterung der Typengenehmigung vom',
    'Erweiterung TG Positionen': 'Erweiterte Positionen',
    'Typengenehmigung erteilt': 'Typengenehmigung erteilt',
    Typengenehmigungsnummer: 'Typengenehmigungsnummer'
  },
  en: {
    'gültig für Importdatum bis': 'Valid for import until',
    'Erweiterung TG vom': 'Type approval extended on',
    'Erweiterung TG Positionen': 'Extended positions',
    'Typengenehmigung erteilt': 'Type approval granted',
    Typengenehmigungsnummer: 'Type approval number'
  },
  tr: {
    'gültig für Importdatum bis': 'İthalat için geçerlilik sonu',
    'Erweiterung TG vom': 'Tip onayı genişletme tarihi',
    'Erweiterung TG Positionen': 'Genişletilen maddeler',
    'Typengenehmigung erteilt': 'Tip onayı veriliş tarihi',
    Typengenehmigungsnummer: 'Tip onay numarası'
  }
};

/** Begriffe nach Abtrennen von Nummer und Zusaetzen. */
const TERMS: Record<string, Dict> = {
  de: {},
  en: {
    // Hersteller-Typ
    Hersteller: 'Manufacturer',
    Fahrzeugart: 'Vehicle category',
    Fahrzeugsubart: 'Vehicle subcategory',
    'Fahrzeugsubart Code': 'Subcategory code',
    Fahrgestellnummer: 'Chassis number',
    Marke: 'Make',
    Typ: 'Type',
    'Typ; Variante/Version': 'Type, variant/version',
    Karosserieform: 'Body style',
    'Karosserieform Code': 'Body style code',
    'EFKO-Code': 'EFKO code',
    Herstellerplakette: 'Manufacturer plate',
    Vorziffer: 'Leading digits (VIN pattern)',
    Fahrzeugklasse: 'Vehicle class',
    'EU-Gesamtgenehmigung': 'EU whole vehicle approval',
    Geländefahrzeug: 'Off-road vehicle',
    // Fahrgestell
    'Fahrzeug Vmax': 'Top speed',
    Getriebe: 'Gearbox',
    iA: 'Final drive ratio',
    Zuordnung: 'Assignment',
    Achsantrieb: 'Driven axles',
    'Achsen/Räder': 'Axles / wheels',
    Lenkung: 'Steering',
    Federung: 'Suspension',
    Betriebsbremse: 'Service brake',
    Hilfsbremse: 'Secondary brake',
    Feststellbremse: 'Parking brake',
    Dauerbremse: 'Endurance brake',
    // Motor
    'Motor Marke': 'Engine make',
    'Motor Typ': 'Engine type',
    Bauart: 'Design',
    'Bauart Treibstoff': 'Fuel',
    Hubraum: 'Displacement',
    'Leistung kW': 'Power',
    'Leistung n': 'Power at engine speed',
    'Md. max Nm': 'Max. torque',
    'Md. max n': 'Torque at engine speed',
    Motorkennzeichen: 'Engine code',
    'Motorkennzeichen Anbringungsort': 'Engine code location',
    Abgasreinigung: 'Emission control',
    'Schalldämpfer Bez': 'Silencer designation',
    'Schalldämpfer Art': 'Silencer type',
    Geräuschdämpfung: 'Noise damping',
    // Ausrüstung-Abmessungen
    Länge: 'Length',
    Breite: 'Width',
    Höhe: 'Height',
    'Überhang vorne': 'Front overhang',
    'Überhang hinten': 'Rear overhang',
    'Anzahl Plätze Total': 'Seats, total',
    'Anzahl Plätze vorne': 'Seats, front',
    'Anzahl Türen': 'Number of doors',
    'Abstand Achse 1-2': 'Wheelbase, axle 1-2',
    'Abstand Achse 2-3': 'Distance, axle 2-3',
    'Abstand Achse 3-4': 'Distance, axle 3-4',
    'Spur Achse': 'Track width, axle',
    'ET Achse': 'Wheel offset, axle',
    Rückspiegel: 'Mirrors',
    // Gewichte-Garantien
    Leergewicht: 'Kerb weight',
    Garantiegewicht: 'Permissible gross weight',
    'Achsgarantie v': 'Front axle limit',
    'Achsgarantie h': 'Rear axle limit',
    Dachlast: 'Roof load',
    'keine Dachlast': 'No roof load',
    // Anhängelast
    gebremst: 'Braked',
    ungebremst: 'Unbraked',
    'mit Auflaufbremse': 'With overrun brake',
    Zentralachsanhänger: 'Centre-axle trailer',
    'Zentralachsanh. /ABS': 'Centre-axle trailer with ABS',
    Drehschemellenkung: 'Turntable steering',
    'Drehschemellenk./ABS': 'Turntable steering with ABS',
    Sattelanhänger: 'Semi-trailer',
    'Sattelanhänger/ABS': 'Semi-trailer with ABS',
    Gesamtzuggewicht: 'Gross combination weight',
    Stützlast: 'Nose weight',
    'Stützlast/Faktor Anh.Vorr.': 'Nose weight / coupling factor',
    'keine Anhängelast': 'No towing capacity',
    // Reifen, Bemerkungen
    'Reifen Felgen': 'Tyres / rims',
    Bemerkungen: 'Remarks'
  },
  tr: {
    // Hersteller-Typ
    Hersteller: 'Üretici',
    Fahrzeugart: 'Araç türü',
    Fahrzeugsubart: 'Araç alt türü',
    'Fahrzeugsubart Code': 'Alt tür kodu',
    Fahrgestellnummer: 'Şasi numarası',
    Marke: 'Marka',
    Typ: 'Tip',
    'Typ; Variante/Version': 'Tip, varyant/versiyon',
    Karosserieform: 'Kasa tipi',
    'Karosserieform Code': 'Kasa tipi kodu',
    'EFKO-Code': 'EFKO kodu',
    Herstellerplakette: 'Üretici etiketi',
    Vorziffer: 'Ön haneler (VIN deseni)',
    Fahrzeugklasse: 'Araç sınıfı',
    'EU-Gesamtgenehmigung': 'AB tam araç onayı',
    Geländefahrzeug: 'Arazi aracı',
    // Fahrgestell
    'Fahrzeug Vmax': 'Azami hız',
    Getriebe: 'Şanzıman',
    iA: 'Diferansiyel oranı',
    Zuordnung: 'Eşleştirme',
    Achsantrieb: 'Çekiş aksları',
    'Achsen/Räder': 'Aks / tekerlek',
    Lenkung: 'Direksiyon',
    Federung: 'Süspansiyon',
    Betriebsbremse: 'Servis freni',
    Hilfsbremse: 'Yardımcı fren',
    Feststellbremse: 'El freni',
    Dauerbremse: 'Yavaşlatıcı fren',
    // Motor
    'Motor Marke': 'Motor markası',
    'Motor Typ': 'Motor tipi',
    Bauart: 'Yapı türü',
    'Bauart Treibstoff': 'Yakıt',
    Hubraum: 'Motor hacmi',
    'Leistung kW': 'Güç',
    'Leistung n': 'Gücün alındığı devir',
    'Md. max Nm': 'Azami tork',
    'Md. max n': 'Torkun alındığı devir',
    Motorkennzeichen: 'Motor kodu',
    'Motorkennzeichen Anbringungsort': 'Motor kodunun yeri',
    Abgasreinigung: 'Egzoz gazı arıtma',
    'Schalldämpfer Bez': 'Susturucu tanımı',
    'Schalldämpfer Art': 'Susturucu tipi',
    Geräuschdämpfung: 'Ses yalıtımı',
    // Ausrüstung-Abmessungen
    Länge: 'Uzunluk',
    Breite: 'Genişlik',
    Höhe: 'Yükseklik',
    'Überhang vorne': 'Ön çıkma',
    'Überhang hinten': 'Arka çıkma',
    'Anzahl Plätze Total': 'Toplam koltuk sayısı',
    'Anzahl Plätze vorne': 'Ön koltuk sayısı',
    'Anzahl Türen': 'Kapı sayısı',
    'Abstand Achse 1-2': 'Dingil mesafesi (aks 1-2)',
    'Abstand Achse 2-3': 'Aks 2-3 mesafesi',
    'Abstand Achse 3-4': 'Aks 3-4 mesafesi',
    'Spur Achse': 'İz genişliği, aks',
    'ET Achse': 'Jant ofseti, aks',
    Rückspiegel: 'Aynalar',
    // Gewichte-Garantien
    Leergewicht: 'Boş ağırlık',
    Garantiegewicht: 'Azami yüklü ağırlık',
    'Achsgarantie v': 'Ön aks azami yükü',
    'Achsgarantie h': 'Arka aks azami yükü',
    Dachlast: 'Tavan yükü',
    'keine Dachlast': 'Tavan yükü yok',
    // Anhängelast
    gebremst: 'Frenli',
    ungebremst: 'Frensiz',
    'mit Auflaufbremse': 'Ataletli frenli',
    Zentralachsanhänger: 'Merkezi akslı römork',
    'Zentralachsanh. /ABS': 'Merkezi akslı römork (ABS)',
    Drehschemellenkung: 'Döner tablalı dümenleme',
    'Drehschemellenk./ABS': 'Döner tablalı dümenleme (ABS)',
    Sattelanhänger: 'Yarı römork',
    'Sattelanhänger/ABS': 'Yarı römork (ABS)',
    Gesamtzuggewicht: 'Katar toplam ağırlığı',
    Stützlast: 'Bağlantı dikey yükü',
    'Stützlast/Faktor Anh.Vorr.': 'Bağlantı yükü / kanca faktörü',
    'keine Anhängelast': 'Römork çekilemez',
    // Reifen, Bemerkungen
    'Reifen Felgen': 'Lastik / jant',
    Bemerkungen: 'Notlar'
  }
};

/** Zusaetze hinter dem Begriff. */
const QUALIFIERS: Record<string, Dict> = {
  de: {von: 'min.', bis: 'max.', mech: 'Schaltgetriebe', autom: 'Automat'},
  en: {von: 'min', bis: 'max', mech: 'manual', autom: 'automatic'},
  tr: {von: 'min', bis: 'maks', mech: 'manuel', autom: 'otomatik'}
};

/**
 * Einen TARGA-Feldnamen in der gewaehlten Sprache beschriften.
 *
 * Unbekannte Begriffe werden unveraendert durchgereicht - lieber der
 * amtliche deutsche Name als gar keiner.
 */
export function specLabel(raw: string, locale: string): string {
  const lang = locale in TERMS ? locale : 'de';
  const trimmed = raw.trim();

  const numbered = /^(\d{2})\s+(.*)$/.exec(trimmed);
  const position = numbered ? numbered[1] : '';
  let rest = (numbered ? numbered[2] : trimmed).replace(/:$/, '').trim();

  const whole = WHOLE[lang]?.[rest] ?? WHOLE.de[rest];
  if (whole) return position ? `${position} ${whole}` : whole;

  const quals: string[] = [];
  rest = rest.replace(/\s+(mech|autom)$/, (_, q: string) => {
    quals.push(QUALIFIERS[lang][q] ?? q);
    return '';
  });
  rest = rest.replace(/\s+(von|bis)$/, (_, q: string) => {
    quals.unshift(QUALIFIERS[lang][q] ?? q);
    return '';
  });

  // Laufende Nummer, hinten ("Getriebe 2", "Bemerkungen Z5") oder in der
  // Mitte ("Schalldämpfer 1 Bez").
  let index = '';
  rest = rest.replace(/\s+Z?(\d+)$/, (_, n: string) => {
    index = n;
    return '';
  });
  rest = rest.replace(/\s+(\d+)\s+/, (_, n: string) => {
    index = n;
    return ' ';
  });

  const term = TERMS[lang]?.[rest.trim()] ?? rest.trim();
  const suffix = quals.length ? ` (${quals.join(', ')})` : '';
  return [position, `${term}${index ? ` ${index}` : ''}${suffix}`]
    .filter(Boolean)
    .join(' ');
}

/** Feldnamen, deren Wert ein Datum im Format JJJJMMTT ist. */
const DATE_FIELDS = /Importdatum|Erweiterung TG vom|Typengenehmigung erteilt/;

/**
 * Werte, die als reine Ziffernfolge ein Datum sind, lesbar machen.
 *
 * Der Rest bleibt unveraendert: die Freitexte des Typenscheins ("siehe
 * Bemerkungen", "Luftfederung") sind amtlicher Wortlaut und werden nicht
 * maschinell uebersetzt.
 */
export function specValue(rawKey: string, value: string, locale: string): string {
  if (!DATE_FIELDS.test(rawKey) || !/^\d{8}$/.test(value.trim())) return value;
  const [y, m, d] = [value.slice(0, 4), value.slice(4, 6), value.slice(6, 8)];
  const date = new Date(Number(y), Number(m) - 1, Number(d));
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(locale, {dateStyle: 'medium'}).format(date);
}
