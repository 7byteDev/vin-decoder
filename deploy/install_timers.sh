#!/usr/bin/env bash
# Richtet die naechtliche Datenpflege als systemd-Timer ein.
# Ubuntu 24.04 minimal bringt kein cron mit - systemd-Timer sind hier
# ohnehin die bessere Wahl (Logs ueber journalctl, kein Extra-Paket).
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/opt/vin-decoder}"

install -d "$PROJECT_DIR/logs"

# --- Import ---------------------------------------------------------------
# Bewusst langsam: 2 Sekunden Abstand je Anfrage, nur Europa/Tuerkei.
# Ein zu schneller Lauf hat vPIC schon einmal dazu gebracht, die gesamte
# oeffentliche IP zu sperren - siehe docs/BETRIEB.md.
cat > /etc/systemd/system/vin-decoder-import.service <<EOF
[Unit]
Description=VIN-Decoder Datenimport (vPIC WMI + vininfo)
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
WorkingDirectory=$PROJECT_DIR
ExecStart=/usr/bin/docker compose run --rm -T etl python -m etl.run_import nhtsa-wmi --focus-only --rate 2.0
ExecStart=/usr/bin/docker compose run --rm -T etl python -m etl.run_import vininfo
TimeoutStartSec=4h
EOF

# --- TARGA-Sync ------------------------------------------------------------
# Das ASTRA aktualisiert die Typengenehmigungen freitags. Wir ziehen sie
# Samstag frueh - dann ist der Lauf der Behoerde sicher durch, und ein
# Fehlschlag hat das Wochenende zum Nachholen (Persistent=true).
# Der Importer laedt die 308-MB-Datei nur, wenn sich Groesse oder
# Last-Modified geaendert haben.
cat > /etc/systemd/system/vin-decoder-targa.service <<EOF
[Unit]
Description=VIN-Decoder TARGA-Sync (Schweizer Typengenehmigungen)
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
WorkingDirectory=$PROJECT_DIR
ExecStart=/usr/bin/docker compose run --rm -T etl python -m etl.run_import targa
# Fahrzeugbilder portionsweise nachladen (Wikimedia Commons, betont langsam).
# Der Lauf merkt sich, welche Modellfamilien er schon geprueft hat, und
# arbeitet den Bestand so ueber die Wochen ab.
# 4 Sekunden Abstand: Wikimedia hat einen frueheren Lauf mit 1,5 s
# grossflaechig gedrosselt (981 Abweisungen). Lieber langsam.
ExecStart=/usr/bin/docker compose run --rm -T etl python -m etl.run_import images --min-approvals 5 --limit 250 --rate 4.0
# Markenlogos (Wikidata P154). Neue Marken kommen selten dazu, der Lauf
# fragt nur die noch ungeprueften ab und ist meist in Sekunden fertig.
ExecStart=/usr/bin/docker compose run --rm -T etl python -m etl.run_import logos --limit 40 --rate 3.5
TimeoutStartSec=4h
EOF

cat > /etc/systemd/system/vin-decoder-targa.timer <<'EOF'
[Unit]
Description=VIN-Decoder TARGA-Sync, woechentlich nach der ASTRA-Aktualisierung

[Timer]
# ASTRA aktualisiert freitags; Samstag 02:30 ist der Lauf sicher fertig.
OnCalendar=Sat *-*-* 02:30:00
RandomizedDelaySec=45m
Persistent=true

[Install]
WantedBy=timers.target
EOF

cat > /etc/systemd/system/vin-decoder-import.timer <<'EOF'
[Unit]
Description=VIN-Decoder Datenimport, taeglich nachts

[Timer]
OnCalendar=*-*-* 03:30:00
RandomizedDelaySec=30m
Persistent=true

[Install]
WantedBy=timers.target
EOF

# --- Sicherung ------------------------------------------------------------
cat > /etc/systemd/system/vin-decoder-backup.service <<EOF
[Unit]
Description=VIN-Decoder Datenbanksicherung
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
WorkingDirectory=$PROJECT_DIR
ExecStart=/usr/bin/bash $PROJECT_DIR/deploy/backup.sh
EOF

cat > /etc/systemd/system/vin-decoder-backup.timer <<'EOF'
[Unit]
Description=VIN-Decoder Sicherung, taeglich

[Timer]
OnCalendar=*-*-* 04:15:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now     vin-decoder-import.timer     vin-decoder-targa.timer     vin-decoder-backup.timer

echo "--- Aktive Timer ---"
systemctl list-timers --no-pager 'vin-decoder-*'
