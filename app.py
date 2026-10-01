"""DonutSMP Market – kleiner lokaler Server.

Der API-Key bleibt hier im Backend (.env) und landet nie im Browser.
Ohne Key läuft automatisch der Demo-Modus mit erfundenen Daten.
"""
import hmac
import math
import os
import random
import time
import zlib

import requests
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request, send_from_directory

load_dotenv()

BASE = "https://api.donutsmp.net/v1"
KEY = os.getenv("DONUTSMP_API_KEY", "").strip()
DEMO = os.getenv("DEMO", "").strip().lower() in ("1", "true", "yes") or not KEY
ORDERS_PATH = os.getenv("ORDERS_PATH", "").strip().strip("/")
AH_METHOD = os.getenv("AH_METHOD", "GET").strip().upper()
APP_PASSWORD = os.getenv("APP_PASSWORD", "").strip()
ALLOW_OPEN = os.getenv("ALLOW_OPEN", "").strip().lower() in ("1", "true", "yes")
ON_HOSTING = bool(os.getenv("PORT"))   # Hosting-Dienste setzen PORT; lokal ist es leer
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_TTL = 15       # Sekunden – schont das Limit von 250 Requests/Minute
PAGE_SIZE = 50       # nur für den Demo-Modus
MAX_SCAN_PAGES = 20

app = Flask(__name__, static_folder=None)
_cache = {}


class UpstreamError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def upstream(path, body=None):
    """Ruft die DonutSMP-API auf (mit kurzem Cache)."""
    ck = (path, repr(sorted((body or {}).items())))
    hit = _cache.get(ck)
    if hit and time.time() - hit[0] < CACHE_TTL:
        return hit[1]
    if len(_cache) > 500:
        _cache.clear()

    url = f"{BASE}/{path}"
    headers = {"Authorization": f"Bearer {KEY}", "Accept": "application/json"}
    order = [AH_METHOD] + [m for m in ("GET", "POST") if m != AH_METHOD]
    last = None
    for method in order:
        try:
            r = requests.request(method, url, headers=headers, json=body or None, timeout=15)
        except requests.RequestException as exc:
            raise UpstreamError(502, f"Keine Verbindung zur API: {exc}")
        if r.ok:
            data = r.json()
            _cache[ck] = (time.time(), data)
            return data
        last = r
        if r.status_code not in (400, 404, 405):
            break
    known = {
        401: "API-Key ungültig oder fehlt (401).",
        403: "Zugriff verweigert (403).",
        429: "Rate Limit erreicht (429) – kurz warten.",
    }
    raise UpstreamError(last.status_code, known.get(last.status_code, f"API-Fehler {last.status_code}: {last.text[:200]}"))


# ---------- Normalisierung (tolerant gegenüber leicht anderen Feldnamen) ----------

def extract_list(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for k in ("result", "results", "data", "entries", "items"):
            if isinstance(data.get(k), list):
                return data[k]
    return []


def pretty(item_id):
    return " ".join(w.capitalize() for w in item_id.split("_"))


def num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def normalize(e):
    item = e.get("item")
    d = item if isinstance(item, dict) else {}
    raw = (d.get("id") or d.get("type") or d.get("material")
           or (item if isinstance(item, str) else None)
           or e.get("item_id") or d.get("display_name") or "unknown")
    iid = str(raw).lower().split(":", 1)[-1].replace(" ", "_")
    name = d.get("display_name") or d.get("name")
    if not isinstance(name, str) or not name.strip():
        name = pretty(iid)
    count = int(num(d.get("count", e.get("count", e.get("amount", 1))), 1)) or 1
    price = num(e.get("price"))
    seller = e.get("seller") or e.get("buyer") or e.get("player")
    if isinstance(seller, dict):
        seller = seller.get("name") or seller.get("username")
    return {
        "id": iid,
        "name": name,
        "count": count,
        "price": price,
        "unit": price / count,
        "seller": seller or "?",
        "time_left": e.get("time_left", e.get("timeLeft")),
    }


# ---------- Demo-Daten ----------

DEMO_ITEMS = {
    "diamond": 900, "netherite_ingot": 24000, "elytra": 180000, "emerald": 350,
    "gold_ingot": 120, "iron_ingot": 60, "totem_of_undying": 5200, "enchanted_golden_apple": 42000,
    "shulker_box": 3800, "beacon": 31000, "ender_pearl": 260, "blaze_rod": 140,
    "obsidian": 90, "experience_bottle": 410, "diamond_sword": 2400, "netherite_pickaxe": 29000,
    "spawner": 950000, "dragon_egg": 4200000, "trident": 18000, "nautilus_shell": 1500,
}
SELLERS = ["Creeper_Kai", "NoahBuilds", "x_Lilly_x", "FarmKing", "PixelFuchs", "Trader_Tom", "Bergmann99", "Mia_MC"]


def demo_all():
    rnd = random.Random(42)  # stabiler Angebotsbestand, Preise driften mit der Zeit
    t = time.time()
    out = []
    for iid, base in DEMO_ITEMS.items():
        phase = (zlib.crc32(iid.encode()) % 628) / 100
        drift = 1 + 0.08 * math.sin(t / 300 + phase)
        for _ in range(rnd.randint(8, 30)):
            mult = rnd.choice([0.9, 1, 1, 1, 1, 1.1, 1.1, 1.25])
            count = 1 if base > 100000 else rnd.choice([1, 1, 8, 16, 32, 64])
            unit = max(1, round(base * mult * drift))
            out.append({
                "item": {"id": "minecraft:" + iid, "count": count},
                "price": unit * count,
                "seller": {"name": rnd.choice(SELLERS)},
                "time_left": rnd.randint(600, 172800),
            })
    rnd.shuffle(out)
    return out


def demo_page(search, sort, page):
    rows = demo_all()
    if search:
        rows = [r for r in rows if search.lower() in r["item"]["id"]]
    key = lambda r: r["price"] / r["item"]["count"]
    if sort == "highest_price":
        rows.sort(key=key, reverse=True)
    elif sort == "lowest_price":
        rows.sort(key=key)
    start = (page - 1) * PAGE_SIZE
    return rows[start:start + PAGE_SIZE]


def demo_orders(page):
    rnd = random.Random(7)
    rows = []
    for iid, base in DEMO_ITEMS.items():
        for _ in range(rnd.randint(1, 4)):
            count = rnd.choice([16, 32, 64, 128, 256])
            rows.append({
                "item": {"id": "minecraft:" + iid, "count": count},
                "price": round(base * 0.85) * count,
                "buyer": {"name": rnd.choice(SELLERS)},
            })
    start = (page - 1) * PAGE_SIZE
    return rows[start:start + PAGE_SIZE]


# ---------- Datenzugriff ----------

def ah_page(search, sort, page):
    if DEMO:
        return demo_page(search, sort, page)
    body = {}
    if search:
        body["search"] = search
    if sort:
        body["sort"] = sort
    return extract_list(upstream(f"auction/list/{page}", body))


# ---------- Routen ----------

@app.errorhandler(UpstreamError)
def on_upstream_error(err):
    return jsonify(error=err.message), (err.status if err.status in (401, 403, 429) else 502)


@app.before_request
def protect():
    """Passwortschutz fürs Hosting: Browser fragt einmal nach (Benutzername egal)."""
    if APP_PASSWORD:
        auth = request.authorization
        ok = auth and hmac.compare_digest((auth.password or "").encode(), APP_PASSWORD.encode())
        if not ok:
            return Response("Passwort nötig", 401, {"WWW-Authenticate": 'Basic realm="Donut Market"'})
    elif ON_HOSTING and not DEMO and not ALLOW_OPEN:
        # Echter Key + öffentlich erreichbar + kein Passwort = andere könnten deinen Key verbrauchen
        return Response("Setze APP_PASSWORD (oder bewusst ALLOW_OPEN=1) in den Umgebungsvariablen, bevor du mit echtem Key online gehst.", 503)


@app.get("/")
def index():
    return send_from_directory(HERE, "index.html")


@app.get("/api/status")
def status():
    return jsonify(demo=DEMO, orders=bool(ORDERS_PATH) or DEMO)


@app.get("/api/ah")
def ah():
    page = max(1, int(request.args.get("page", 1)))
    rows = ah_page(request.args.get("search", "").strip(), request.args.get("sort", "lowest_price"), page)
    return jsonify(listings=[normalize(r) for r in rows], page=page)


@app.get("/api/ah/scan")
def ah_scan():
    search = request.args.get("search", "").strip()
    sort = request.args.get("sort", "lowest_price")
    pages = min(max(1, int(request.args.get("pages", 3))), MAX_SCAN_PAGES)
    listings = []
    done = 0
    for p in range(1, pages + 1):
        rows = ah_page(search, sort, p)
        done = p
        if not rows:
            break
        listings.extend(normalize(r) for r in rows)
    return jsonify(listings=listings, pages=done)


@app.get("/api/orders")
def orders():
    page = max(1, int(request.args.get("page", 1)))
    if DEMO:
        rows = demo_orders(page)
    elif ORDERS_PATH:
        rows = extract_list(upstream(f"{ORDERS_PATH}/{page}"))
    else:
        return jsonify(error="Für /orders ist noch kein API-Pfad hinterlegt (ORDERS_PATH in der .env)."), 501
    return jsonify(orders=[normalize(r) for r in rows], page=page)


@app.get("/api/raw")
def raw():
    """Debug: zeigt die ersten Rohdaten der API, um die Feldnamen zu prüfen."""
    page = max(1, int(request.args.get("page", 1)))
    rows = ah_page(request.args.get("search", "").strip(), request.args.get("sort", "lowest_price"), page)
    return jsonify(first_entries=rows[:3], total_on_page=len(rows))


if __name__ == "__main__":
    print("Demo-Modus" if DEMO else "Live-Modus mit deinem API-Key")
    host = os.getenv("HOST", "127.0.0.1").strip()
    print(f"Läuft auf http://{host}:5000")
    app.run(host=host, port=5000, debug=False)
