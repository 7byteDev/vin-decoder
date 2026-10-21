# Betrieb

## Zielsystem

| | |
|---|---|
| Host | `vin.ukm.net.tr` (192.168.8.211) |
| OS | Ubuntu 24.04.3 LTS, Kernel 6.8 |
| Ressourcen | 8 vCPU, 7,8 GB RAM, 98 GB Platte |
| Docker | 29.8.0, Compose v5.5.1 |
| Projektpfad | `/opt/vin-decoder` |
| Zugang | SSH-Key `~/.ssh/vindecoder_vps` (ed25519), Benutzer `root` |

Ports sind über `BIND_ADDRESS` in der `.env` gesteuert. Auf dieser VM steht
`0.0.0.0`, damit die Oberfläche im LAN erreichbar ist:

- <http://192.168.8.211:3000> – Weboberfläche
- <http://192.168.8.211:8000/docs> – API-Dokumentation

Die Datenbank hat bewusst **keine** Portfreigabe und ist nur im Compose-Netz
erreichbar.

## Erstinstallation

```bash
scp deploy/setup_vps.sh root@HOST:/root/ && ssh root@HOST bash /root/setup_vps.sh
```

Das Skript ist idempotent und installiert Docker samt Compose, Basiswerkzeuge,
Log-Rotation für Container und automatische Sicherheitsupdates.

Danach Projekt übertragen, `.env` anlegen (Passwort auf dem Server erzeugen,
nicht lokal tippen) und starten:

```bash
docker compose up -d db api frontend
docker compose run --rm etl python -m etl.run_import migrate
```

## Datenimport

```bash
docker compose run --rm etl python -m etl.run_import vininfo
docker compose run --rm etl python -m etl.run_import nhtsa-wmi --focus-only
docker compose run --rm etl python -m etl.run_import targa
docker compose run --rm etl python -m etl.run_import status
```

### Automatischer Ablauf

| Timer | Zeitpunkt | Inhalt |
|---|---|---|
| `vin-decoder-targa.timer` | **samstags 02:30** | Schweizer Typengenehmigungen. Das ASTRA aktualisiert freitags; die Datei (308 MB) wird nur geladen, wenn sich Größe oder Last-Modified geändert haben. |
| `vin-decoder-import.timer` | täglich 03:30 | WMI-Stammdaten (vPIC, gedrosselt) und vininfo-Regeln |
| `vin-decoder-backup.timer` | täglich 04:15 | Datenbank-Dump |

```bash
systemctl list-timers 'vin-decoder-*'          # Status
journalctl -u vin-decoder-targa.service -n 50  # letzter Lauf
systemctl start vin-decoder-targa.service      # von Hand anstossen
```

### Wichtig: vPIC nicht überfahren

**Der erste Importversuch hat die öffentliche IP bei vPIC in eine
403-Sperre laufen lassen** – acht parallele Verbindungen ohne Pause, nach rund
500 Anfragen war Schluss, betroffen war der gesamte Anschluss (auch Arbeitsplatz-
rechner). Die Sperre löste sich nach etwa zehn Minuten von selbst.

Daraus folgen drei Dinge, die jetzt im Code stehen:

1. **`--focus-only` filtert die Herstellerliste vor dem Abruf.** vPIC führt
   22.988 Hersteller, davon liegen nur **679 in Europa/Türkei** (66 in der
   Türkei) – der Rest sind überwiegend US-Anhänger- und Aufbauhersteller. Der
   Filter senkt den Lauf von 22.988 auf 679 Anfragen.
2. **Voreinstellung ist eine Anfrage pro Sekunde bei zwei Verbindungen**
   (`--rate`, `--concurrency`). Der volle Lauf ohne Filter dauert damit
   mehrere Stunden – das ist beabsichtigt und gehört in einen Nacht-Job.
3. **Bei 403/429/503 wird gewartet, nicht weitergefeuert.** Nach fünf Sperren
   in Folge bricht der Lauf sauber ab; der Plattencache bleibt erhalten, ein
   späterer Lauf setzt dort auf.

Wenn doch einmal eine Sperre auftritt: nichts weiter versuchen, zehn bis
dreißig Minuten warten, dann mit größerem `--rate` neu starten.

## Sicherung

Die Datenbank ist reproduzierbar – alle Daten stammen aus wiederholbaren
Importen. Trotzdem spart ein Dump den mehrstündigen Neuaufbau:

```bash
bash deploy/backup.sh          # legt /var/backups/vin-decoder/vindb-<datum>.sql.gz an
```

Sinnvoll als täglicher Cron-Job. Zusätzlich sichernswert: `/opt/vin-decoder/.env`
(enthält das DB-Passwort) und das Volume `vin-decoder_etl-cache` (spart beim
Neuaufbau die vPIC-Abrufe).

## Offene Härtungsschritte

Bewusst noch **nicht** umgesetzt, weil sie über „Projekt zum Laufen bringen"
hinausgehen und dich aussperren können:

- Root-Passwort ändern (`ankara` stand im Klartext in einem Chatverlauf).
- Passwort-Anmeldung per SSH abschalten (`PasswordAuthentication no`), nachdem
  der Key sicher funktioniert.
- `ufw` mit `allow 22`, `allow 3000`, `allow 8000` und `enable`.
- Reverse Proxy mit TLS (Caddy oder nginx) vor die beiden Dienste, sobald das
  Tool über `vin.ukm.net.tr` von außen erreichbar sein soll. Erst dann sollte
  `BIND_ADDRESS` wieder auf `127.0.0.1` und der Proxy davor.
