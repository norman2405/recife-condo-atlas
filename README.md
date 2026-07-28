# Recife Condo Atlas – Phase 1

Dies ist eine echte statische Progressive Web App (PWA). Das Paket enthält nur Dateien, die für die Veröffentlichung benötigt werden.

## Enthalten

- `index.html`
- `styles.css`
- `app.js`
- `manifest.webmanifest`
- `service-worker.js`
- `icons/`
- `data/`

## Funktionen

- Gebäudesuche und Stadtteilfilter
- Anzeigenübersicht
- Schnellfilter nach Preis, Schlafzimmern, Etage, Meerblick und Varanda
- Gebäudedetails und zugeordnete Anzeigen
- Favoriten im lokalen Gerätespeicher
- installierbar auf dem iPhone
- Offline-Cache nach dem ersten vollständigen Laden

## Veröffentlichung über GitHub Pages

1. Ein öffentliches GitHub-Repository erstellen.
2. **Den Inhalt dieses Ordners** direkt in das Hauptverzeichnis hochladen. `index.html` muss auf der obersten Ebene liegen.
3. Unter `Settings > Pages` die Quelle `Deploy from a branch`, Branch `main`, Ordner `/root` wählen.
4. Die erzeugte GitHub-Pages-Adresse in Safari öffnen.
5. In Safari: Teilen > Zum Home-Bildschirm.

Die App funktioniert nicht korrekt, wenn `index.html` nur lokal aus der Dateien-App geöffnet wird, weil Browser lokale JSON-Dateien aus Sicherheitsgründen blockieren können.

## Datenhinweis

Die App verwendet einen statischen Snapshot der vorhandenen Atlas-Daten. Angebotspreise sind keine tatsächlichen Verkaufspreise. Nicht verifizierte oder fehlende Angaben werden als offen angezeigt.
