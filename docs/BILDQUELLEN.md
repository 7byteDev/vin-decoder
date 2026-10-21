# Fahrzeugbilder: Untersuchung und Plan

Stand: 2026-09-09. Anlass: die angezeigten Fotos sind zwar inzwischen
generationsrichtig, sehen sich aber untereinander zu ähnlich (dunkle
Limousine, Heck-Dreiviertel, Verkehrssituation) und wirken nicht
professionell. Diese Notiz hält fest, woran das liegt, welche Quellen
tatsächlich in Frage kommen und in welcher Reihenfolge nachgebessert wird.

## 1 Befund

Der Bildimport läuft heute in drei Stufen: Wikidata-Hauptbild (P18), die
Commons-Kategorie der Generation, danach die Commons-Volltextsuche. Die
Volltextsuche liefert den Großteil der Treffer – und genau sie ist das
Problem.

| Quelle | Anteil im Bestand | Charakter |
|---|---|---|
| `commons_search` (Volltext) | 1050 | beliebige Straßenaufnahmen |
| `commons_category` | 287 | gepflegt, generationsrein |
| `wikidata_p18` | 43 | kuratiert, meist die beste Aufnahme |

Die Volltextsuche kennt keinen Qualitätsbegriff. Sie bewertet
Wortübereinstimmung, nicht Bildqualität. Massenuploads von
Straßenfotografie (Serien wie `… China (12).jpg`) dominieren deshalb das
Ergebnis: dasselbe Fahrzeug, dieselbe Perspektive, unruhiger Hintergrund,
fremde Autos im Bild. Ein Unfallwagen war der Extremfall davon, kein
Einzelfehler.

**Wichtig:** die Fotos sind nicht falsch. Sie zeigen die richtige
Baureihe. Was fehlt, ist eine Auswahl nach *Qualität* und *Vielfalt*.

## 2 Geprüfte Signale und Quellen

### 2.1 Commons-Suchoperatoren (CirrusSearch) – geprüft, funktioniert

Die Commons-Suche kann mehr als Volltext. Drei Operatoren sind für uns
entscheidend und wurden am lebenden System getestet:

| Operator | Wirkung | Messung |
|---|---|---|
| `deepcategory:"<Kategorie>"` | sucht im ganzen Kategoriebaum der Generation | generationsrein |
| `incategory:"Quality images"` | nur von der Community ausgezeichnete Fotos | 17 682 Fahrzeugfotos insgesamt |
| `fileres:>2000` | Mindestauflösung | pro Generation 200–2800 Treffer |

Beispielmessung je Generation (Anzahl Treffer):

| Generation | mit Gütesiegel | hochauflösend |
|---|---|---|
| Mercedes-Benz W223 | 10 | 114 |
| BMW G05 (X5) | 14 | 369 |
| Audi A3 8V | 20 | 548 |
| Fiat Ducato | 20 | 796 |
| Ford Transit | 51 | 2810 |
| VW Tiguan I | 1 | 229 |

„Quality images" ist ein Peer-Review-Siegel: Schärfe, Belichtung,
Bildaufbau werden von anderen Commons-Autoren geprüft. Das ist genau der
Qualitätsbegriff, der uns bisher fehlt – und er kostet nichts, weil die
Lizenzlage dieselbe bleibt.

Zwei Einschränkungen, beide gemessen:

* Das Siegel sagt nichts über das *Motiv*. Unter den ausgezeichneten
  Ducato-Bildern liegt eine Straßenszene aus Recife und ein Polizeiwagen.
  Die vorhandene Bewertung und die Ausschlussliste bleiben also nötig.
* Ausgezeichnete Detailaufnahmen kommen vor („VW Golf VII – Fuel filler").
  Auch das fängt die Ausschlussliste ab.

### 2.2 Kategoriename der Generation – die eigentliche Hürde

`deepcategory` ist nur so gut wie der Kategoriename. Die Konventionen
unterscheiden sich je Hersteller:

* Mercedes-Benz: `Mercedes-Benz W223` – aus der VIN ableitbar
* BMW: `BMW G05` – aus dem Baureihencode
* Audi: `Audi A4 B8` – Modell plus Plattform
* VW Golf: **nicht** `Volkswagen Golf Mk7` (0 Treffer), sondern die
  römische Schreibweise

Ein geratener Name kostet einen Fehlschlag pro Generation. Verlässlich
ist nur der Weg über Wikidata: das Generationsobjekt trägt die
Eigenschaft P373 (Commons-Kategorie). Den Abgleich Generation ↔
Wikidata-Objekt gibt es bereits (über den Bauzeitraum), er wird bisher
nur für kurze Modellnamen übersprungen.

### 2.3 Weitere Quellen

| Quelle | Lizenz | Generationsbezug | Bewertung |
|---|---|---|---|
| **Wikimedia Commons** | CC/PD, sauber | über Kategoriebaum sehr gut | bleibt Basis |
| **Openverse** (openverse.org) | CC/PD, filterbar | keiner – reine Stichwortsuche | kein Gewinn gegenüber Commons, speist sich großteils daraus |
| **Flickr** mit CC-Filter | CC-BY/CC0, sauber | schwach, aber Messearchive sind gut verschlagwortet | sinnvolle **zweite** Quelle, API-Schlüssel kostenlos |
| **Hersteller-Presseportale** (Mercedes-Benz Media, Audi MediaCenter, BMW PressClub, Stellantis, VW Newsroom) | **keine freie Lizenz** – redaktionelle Nutzung, Registrierung, kein automatisierter Massenabruf | perfekt | scheidet nach Abschnitt 9 des Projektplans aus |
| **Stockdienste** (Unsplash, Pexels, Pixabay) | frei | keiner – kennen keine Baureihen | untauglich |
| **carimagery.com** | unklar, Hobbydienst | grob | niedrige Auflösung, keine Zusage zur Verfügbarkeit |

Ergebnis: eine kostenlose, rechtlich saubere, nach Marke/Modell/Generation
geordnete Bilddatenbank für europäische Fahrzeuge existiert nicht. Was
ihr am nächsten kommt, ist der Commons-Kategoriebaum – vorausgesetzt, man
fragt ihn richtig ab. Genau das ist Stufe 1 des Plans.

## 3 Plan

### Stufe 1 – Abfrage auf Kategoriebaum und Gütesiegel umstellen

Die Volltextsuche verliert ihre Vorrangstellung. Neue Reihenfolge:

1. `deepcategory:"<Kategorie>" incategory:"Quality images"` – ausgezeichnete Fotos der Generation
2. `deepcategory:"<Kategorie>" fileres:>2000` – hochauflösende Fotos der Generation
3. Wikidata-Hauptbild (P18) der Generation
4. Volltextsuche – nur, wenn 1–3 zusammen nicht genügend Treffer liefern

Erwartete Wirkung: der Anteil zufälliger Straßenaufnahmen sinkt von rund
drei Vierteln auf einen Rest.

### Stufe 2 – Kategoriename verlässlich bestimmen

* P373 des Generationsobjekts als erste Quelle.
* Fehlt sie, die herstellerspezifische Konvention als Kandidat prüfen und
  das Ergebnis in der Datenbank vermerken, damit kein Rateversuch
  wiederholt wird.
* Der Wikidata-Abgleich läuft künftig auch für kurze Modellnamen („S"),
  weil die Baureihe aus der VIN (`W223`) den Suchbegriff liefert.

### Stufe 3 – Vielfalt erzwingen

Sechs Aufnahmen desselben Fahrzeugs aus derselben Fotosession sind
schlechter als drei verschiedene Fahrzeuge. Regeln:

* höchstens zwei Bilder je Urheber
* höchstens zwei Bilder je Aufnahmeserie (erkennbar am Dateinamenmuster
  `1X7A0206`, `IMG 0266`, `DSC 7199`)
* bevorzugt gemischte Ansichten (Front / Seite / Heck) statt sechsmal
  Heck-Dreiviertel

### Stufe 4 – Flickr als zweite Quelle (optional, nach Entscheidung)

Nur wenn Stufe 1–3 die Lücken nicht schließen. Suche mit
`license=4,5,9,10` (CC-BY, CC-BY-SA, CC0, PDM), Suchbegriff aus Marke und
Baureihe, zusätzlich Messebegriffe. Namensnennung wie bei Commons.
Aufwand: etwa ein halber Tag.

### Nicht vorgesehen

Hersteller-Presseportale und kommerzielle Bilddatenbanken. Die Lizenz
erlaubt weder den automatisierten Abruf noch die Weiterverwendung; das
bleibt auch für ein privates Projekt so. Wer Bilder von dort einsetzen
will, lädt sie selbst herunter – dafür lässt sich eine lokale Ablage
anbinden, die über die Baureihe zugeordnet wird.

## 4 Messgrößen

Nach Stufe 1–3 wird nachgemessen:

* Anteil der Bilder aus kuratierten Quellen (Ziel: über 70 %, heute 24 %)
* Generationen mit mindestens drei Bildern (heute: Bestand im Aufbau)
* Stichprobe von 20 Detailseiten: zeigt jede Galerie mindestens zwei
  deutlich verschiedene Ansichten?
