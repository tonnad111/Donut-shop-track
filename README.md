# Donut Market

Web-Plattform für das DonutSMP-Auktionshaus: alle Angebote durchsuchen, Preisstufen mit Stückzahlen sehen, Items auf eine Watchlist legen und den Preisverlauf mitverfolgen.

Dateien: `app.py` (Server), `index.html` (Oberfläche), `requirements.txt`.

## Nur mit iPad/Handy online stellen (Render)

1. **ZIP entpacken:** Auf dem iPad in der Dateien-App auf die ZIP tippen.
2. **GitHub:** Account auf github.com anlegen, oben rechts "+" → "New repository", Namen vergeben (z. B. `donut-market`), "Create repository".
3. **Dateien hochladen:** "uploading an existing file" antippen und `app.py`, `index.html` und `requirements.txt` auswählen, dann "Commit changes".
4. **Render:** Auf render.com mit GitHub anmelden → "New" → "Web Service" → dein Repo wählen und:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app --workers 1 --threads 4`
   - Instance Type: Free
5. **Umgebungsvariablen** (unter "Environment"):
   - `APP_PASSWORD` = ein Passwort deiner Wahl
   - `DONUTSMP_API_KEY` = dein Key (erst setzen, wenn du ihn hast; ohne Key läuft der Demo-Modus)
6. "Create Web Service". Nach dem Deploy bekommst du eine Adresse wie `donut-market.onrender.com`. Beim Öffnen fragt der Browser nach einem Passwort (Benutzername egal).

Hinweise:
- Der kostenlose Render-Tarif schläft nach einiger Zeit ein. Der erste Aufruf danach dauert etwa eine Minute.
- Die Watchlist liegt im Browser jedes Geräts. iPad und Handy haben getrennte Listen, und der Verlauf läuft nur mit, solange die Seite offen ist.
- Mit echtem Key und ohne `APP_PASSWORD` sperrt sich der Server absichtlich.

## Lokal auf einem PC

```bash
pip install -r requirements.txt
cp .env.example .env
python app.py        # http://127.0.0.1:5000
```

Für iPad im gleichen WLAN: in der `.env` `HOST=0.0.0.0` setzen und am iPad `http://<PC-IP>:5000` öffnen.

## Annahmen, die du prüfen solltest

Die offizielle API-Doku konnte ich nicht direkt lesen, nur die Endpunkt-Liste aus einem Community-Projekt.

1. **Feldnamen:** Das Backend erkennt `item.id`, `item.count`, `price`, `seller`, `time_left` tolerant. Wenn etwas leer oder falsch ankommt, öffne `/api/raw?search=diamond` und schick die Ausgabe.
2. **Suche/Sortierung:** `search` und `sort` gehen als JSON-Body raus (zuerst GET, bei Fehler POST). Mit `AH_METHOD=POST` drehst du die Reihenfolge um.
3. **/orders:** Ein Endpunkt dafür ist mir nicht bekannt. Trag den Pfad als `ORDERS_PATH` ein, sobald du ihn kennst. Im Demo-Modus gibt es Fake-Orders.

## Limits

250 Requests pro Minute pro Key. Antworten werden 15 Sekunden gecacht.
