#!/usr/bin/env python3
"""
Encar -> Telegram bot.
Sprawdza wyszukiwanie na car.encar.com i wysyła na Telegram nowe ogłoszenia
oraz obniżki cen. Tylko biblioteka standardowa Pythona (bez instalowania paczek).

Tryby:
  python bot.py                 jedno sprawdzenie (GitHub Actions / cron)
  python bot.py --loop 600      sprawdzaj co 600 s (komputer / telefon)
  python bot.py --chat-id       pokaż chat_id (najpierw napisz coś do bota)
  python bot.py --test          wyślij testową wiadomość na Telegram

Konfiguracja (zmienne środowiskowe albo plik config.env obok skryptu):
  TELEGRAM_TOKEN    token od @BotFather
  TELEGRAM_CHAT_ID  Twój chat_id
  SEARCH_URL        (opcjonalnie) link do wyszukiwania na Encar
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(HERE, "seen.json")

DEFAULT_SEARCH_URL = (
    "https://car.encar.com/list/car?page=1&search=%7B%22type%22%3A%22car%22%2C%22action%22%3A%22(And.Hidden.N._.(Or.Separation.F._.Separation.B.)_.SellType.%EC%9D%BC%EB%B0%98._.(C.CarType.Y._.(C.Manufacturer.%EA%B8%B0%EC%95%84._.(C.ModelGroup.%EC%8A%A4%ED%8C%85%EC%96%B4._.(C.Model.%EC%8A%A4%ED%8C%85%EC%96%B4%20%EB%A7%88%EC%9D%B4%EC%8A%A4%ED%84%B0._.(Or.(C.BadgeGroup.%EA%B0%80%EC%86%94%EB%A6%B0%202WD._.(Or.Badge.3_.3%20GT._.Badge.3_.3%20GT%20%EB%A7%88%EC%8A%A4%ED%84%B0%EC%A6%88%20%ED%84%B0%EB%B3%B4%20%ED%8C%A8%ED%82%A4%EC%A7%80._.Badge.3_.3%20GT%20%EC%95%84%ED%81%AC%EB%A1%9C%20%EC%97%90%EB%94%94%EC%85%98._.Badge.3_.3%20GT%20%ED%8A%B8%EB%A6%AC%EB%B7%B0%ED%8A%B8%20%EC%97%90%EB%94%94%EC%85%98.))_.(C.BadgeGroup.%EA%B0%80%EC%86%94%EB%A6%B0%204WD._.(Or.Badge.3_.3%20GT%20AWD%20%ED%8A%B8%EB%A6%AC%EB%B7%B0%ED%8A%B8%20%EC%97%90%EB%94%94%EC%85%98._.Badge.3_.3%20GT%20AWD%20%EC%95%84%ED%81%AC%EB%A1%9C%20%EC%97%90%EB%94%94%EC%85%98._.Badge.3_.3%20GT%20AWD%20%EB%A7%88%EC%8A%A4%ED%84%B0%EC%A6%88%20%ED%84%B0%EB%B3%B4%20%ED%8C%A8%ED%82%A4%EC%A7%80._.Badge.3_.3%20GT%20AWD.))))))))%22%2C%22title%22%3A%22Kia%20Stinger%20Meister(20~23%EB%85%84)%22%2C%22toggle%22%3A%7B%22modelGroup%22%3A1%7D%2C%22layer%22%3A%22%22%2C%22sort%22%3A%22MobilePriceAsc%22%7D"
)

API_URL = "https://api.encar.com/search/car/list/general"
PAGE_SIZE = 50
MAX_PAGES = 20
PHOTO_BASE = "https://ci.encar.com/carpicture"
DETAIL_URL = "https://fem.encar.com/cars/detail/{id}"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")

# Słowniczek, żeby wiadomości były po polsku
KO_PL = {
    "기아": "Kia", "스팅어 마이스터": "Stinger Meister", "스팅어": "Stinger",
    "마스터즈 터보 패키지": "Masters Turbo Package", "아크로 에디션": "Acro Edition",
    "트리뷰트 에디션": "Tribute Edition", "가솔린": "benzyna", "디젤": "diesel",
    "서울": "Seul", "경기": "Gyeonggi", "인천": "Incheon", "부산": "Busan",
    "대구": "Daegu", "대전": "Daejeon", "광주": "Gwangju", "울산": "Ulsan",
    "세종": "Sejong", "강원": "Gangwon", "충북": "Chungbuk", "충남": "Chungnam",
    "전북": "Jeonbuk", "전남": "Jeonnam", "경북": "Gyeongbuk", "경남": "Gyeongnam",
    "제주": "Jeju", "년": "",
}


def tr(text):
    text = str(text or "")
    for ko, pl in sorted(KO_PL.items(), key=lambda kv: -len(kv[0])):
        text = text.replace(ko, pl)
    return text.strip()


# ---------- konfiguracja ----------

def load_config():
    path = os.path.join(HERE, "config.env")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return {
        "token": os.environ.get("TELEGRAM_TOKEN", "").strip(),
        "chat_id": os.environ.get("TELEGRAM_CHAT_ID", "").strip(),
        "search_url": os.environ.get("SEARCH_URL", "").strip() or DEFAULT_SEARCH_URL,
    }


def parse_search_url(url):
    """Z linku car.encar.com wyciąga filtr wyszukiwania (action) i tytuł."""
    qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    if "search" not in qs:
        raise SystemExit("SEARCH_URL nie zawiera parametru 'search' - skopiuj pełny link z wynikami z car.encar.com")
    search = json.loads(qs["search"][0])
    return search["action"], search.get("title") or "Encar"


# ---------- Encar ----------

def http_get_json(url, headers=None, timeout=30):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_listings(action):
    headers = {
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://car.encar.com/",
        "Origin": "https://car.encar.com",
    }
    cars, total = [], None
    for page in range(MAX_PAGES):
        params = urllib.parse.urlencode({
            "count": "true",
            "q": action,
            "sr": f"|ModifiedDate|{page * PAGE_SIZE}|{PAGE_SIZE}",
        }, quote_via=urllib.parse.quote)
        data = None
        for attempt in range(3):
            try:
                data = http_get_json(f"{API_URL}?{params}", headers)
                break
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                if attempt == 2:
                    raise RuntimeError(f"Nie udało się pobrać danych z Encar: {e}")
                time.sleep(5 * (attempt + 1))
        results = data.get("SearchResults") or []
        total = data.get("Count", total)
        cars.extend(results)
        if len(results) < PAGE_SIZE or (total is not None and len(cars) >= total):
            break
        time.sleep(1)
    return cars, total


def car_info(c):
    cid = str(c.get("Id") or c.get("id") or "")
    year = c.get("FormYear") or str(int(c.get("Year") or 0))[:4]
    ym = str(int(c.get("Year") or 0))
    month = ym[4:6] if len(ym) >= 6 else ""
    photo = None
    photos = c.get("Photos") or []
    if photos and isinstance(photos, list):
        loc = photos[0].get("location") if isinstance(photos[0], dict) else None
        if loc:
            photo = PHOTO_BASE + loc
    if not photo and c.get("Photo"):
        photo = PHOTO_BASE + str(c["Photo"]) + "001.jpg"
    # jeśli zdjęcie się nie załaduje, bot i tak wyśle wiadomość bez niego
    return {
        "id": cid,
        "title": " ".join(x for x in [tr(c.get("Manufacturer")), tr(c.get("Model")), tr(c.get("Badge")),
                                       tr(c.get("BadgeDetail"))] if x),
        "year": year,
        "month": month,
        "mileage": int(c.get("Mileage") or 0),
        "price": int(c.get("Price") or 0),          # w 만원 (10 000 KRW)
        "city": tr(c.get("OfficeCityState")),
        "fuel": tr(c.get("FuelType")),
        "photo": photo,
        "url": DETAIL_URL.format(id=cid),
    }


def fmt_price(manwon):
    if not manwon or manwon >= 9999:
        return "cena do uzgodnienia"
    krw = manwon * 10_000
    return f"{krw / 1_000_000:.1f} mln KRW".replace(".", ",") + f" ({manwon:,} 만원)".replace(",", " ")


def fmt_km(km):
    return f"{km:,}".replace(",", " ") + " km"


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def message_new(car):
    date = f"{car['month']}/{car['year']}" if car["month"] else car["year"]
    lines = [
        "🆕 <b>Nowe ogłoszenie</b>",
        f"<b>{esc(car['title'])}</b>",
        f"💰 {esc(fmt_price(car['price']))}",
        f"📅 {esc(date)}   🛣 {esc(fmt_km(car['mileage']))}",
    ]
    if car["city"]:
        lines.append(f"📍 {esc(car['city'])}")
    lines.append(f'<a href="{car["url"]}">Otwórz ogłoszenie</a>')
    return "\n".join(lines)


def message_drop(car, old_price):
    diff = old_price - car["price"]
    return "\n".join([
        "📉 <b>Obniżka ceny</b>",
        f"<b>{esc(car['title'])}</b>",
        f"{esc(fmt_price(old_price))} → <b>{esc(fmt_price(car['price']))}</b>",
        f"(taniej o {diff * 10_000 / 1_000_000:.1f} mln KRW)".replace(".", ","),
        f"📅 {esc(car['year'])}   🛣 {esc(fmt_km(car['mileage']))}",
        f'<a href="{car["url"]}">Otwórz ogłoszenie</a>',
    ])


# ---------- Telegram ----------

def tg(token, method, payload):
    data = urllib.parse.urlencode(payload).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/{method}", data=data)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="ignore")
        if e.code == 429:  # za dużo wiadomości naraz
            try:
                wait = json.loads(body)["parameters"]["retry_after"]
            except Exception:
                wait = 5
            time.sleep(wait + 1)
            return tg(token, method, payload)
        return {"ok": False, "description": body}


def send(cfg, text, photo=None):
    if photo:
        r = tg(cfg["token"], "sendPhoto", {"chat_id": cfg["chat_id"], "photo": photo,
                                           "caption": text, "parse_mode": "HTML"})
        if r.get("ok"):
            return True
    r = tg(cfg["token"], "sendMessage", {"chat_id": cfg["chat_id"], "text": text,
                                         "parse_mode": "HTML", "disable_web_page_preview": "false"})
    if not r.get("ok"):
        print("Błąd Telegrama:", r.get("description"), file=sys.stderr)
    return r.get("ok", False)


# ---------- stan ----------

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return None


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1, sort_keys=True)


# ---------- główna logika ----------

def check(cfg):
    action, title = parse_search_url(cfg["search_url"])
    raw, total = fetch_listings(action)
    cars = [car_info(c) for c in raw]
    cars = [c for c in cars if c["id"]]
    current = {c["id"]: c for c in cars}
    state = load_state()
    now = time.strftime("%Y-%m-%d %H:%M")

    if state is None or state.get("search") != action:
        # pierwsze uruchomienie: zapamiętaj obecne ogłoszenia, bez spamu
        cheapest = min((c for c in cars if 0 < c["price"] < 9999), key=lambda c: c["price"], default=None)
        msg = (f"✅ <b>Bot uruchomiony</b>\nŚledzę: {esc(tr(title))}\n"
               f"Aktualnie ogłoszeń: <b>{len(cars)}</b>\n"
               "Od teraz dostaniesz tylko nowe ogłoszenia i obniżki cen.")
        if cheapest:
            msg += f'\n\nNajtańszy teraz: <a href="{cheapest["url"]}">{esc(cheapest["title"])}</a>, {esc(fmt_price(cheapest["price"]))}'
        send(cfg, msg)
        save_state({"search": action, "cars": {i: c["price"] for i, c in current.items()}, "updated": now})
        print(f"[{now}] Pierwsze uruchomienie, zapamiętano {len(cars)} ogłoszeń.")
        return

    seen = state.get("cars", {})
    new_cars = [c for c in cars if c["id"] not in seen]
    drops = [(c, seen[c["id"]]) for c in cars
             if c["id"] in seen and 0 < c["price"] < seen[c["id"]] and seen[c["id"]] < 9999]

    for c in sorted(new_cars, key=lambda c: c["price"]):
        send(cfg, message_new(c), c["photo"])
        time.sleep(1)
    for c, old in drops:
        send(cfg, message_drop(c, old), c["photo"])
        time.sleep(1)

    # aktualizuj stan; ogłoszenia, które zniknęły, trzymamy jeszcze 30 dni,
    # żeby ponowne wystawienie tego samego auta nie wyglądało jak nowe
    merged = dict(seen)
    for i, c in current.items():
        merged[i] = c["price"]
    gone = state.get("gone", {})
    for i in list(merged):
        if i not in current:
            gone.setdefault(i, now)
            if time.mktime(time.strptime(gone[i], "%Y-%m-%d %H:%M")) < time.time() - 30 * 86400:
                merged.pop(i)
                gone.pop(i)
        else:
            gone.pop(i, None)
    save_state({"search": action, "cars": merged, "gone": gone, "updated": now})
    print(f"[{now}] Ogłoszeń: {len(cars)}, nowych: {len(new_cars)}, obniżek: {len(drops)}")


def main():
    cfg = load_config()
    args = sys.argv[1:]
    if not cfg["token"]:
        raise SystemExit("Brak TELEGRAM_TOKEN (wpisz go do config.env albo do sekretów GitHuba).")

    if "--chat-id" in args:
        r = http_get_json(f"https://api.telegram.org/bot{cfg['token']}/getUpdates")
        chats = {}
        for u in r.get("result", []):
            m = u.get("message") or u.get("channel_post") or {}
            ch = m.get("chat")
            if ch:
                chats[ch["id"]] = ch.get("first_name") or ch.get("title") or ""
        if not chats:
            print("Nic nie znaleziono. Napisz najpierw dowolną wiadomość do swojego bota na Telegramie i spróbuj ponownie.")
        for cid, name in chats.items():
            print(f"chat_id: {cid}   ({name})")
        return

    if not cfg["chat_id"]:
        raise SystemExit("Brak TELEGRAM_CHAT_ID. Uruchom: python bot.py --chat-id")

    if "--test" in args:
        ok = send(cfg, "👋 Test działa. Bot Encar może wysyłać Ci wiadomości.")
        print("Wysłano." if ok else "Nie udało się wysłać - sprawdź token i chat_id.")
        return

    if "--loop" in args:
        i = args.index("--loop")
        every = int(args[i + 1]) if len(args) > i + 1 else 600
        print(f"Sprawdzam co {every} s. Zatrzymanie: Ctrl+C")
        errors = 0
        while True:
            try:
                check(cfg)
                errors = 0
            except Exception as e:
                errors += 1
                print("Błąd:", e, file=sys.stderr)
                if errors == 3:
                    send(cfg, f"⚠️ Bot Encar ma problem z pobieraniem danych:\n{esc(e)}")
            time.sleep(every)
    else:
        check(cfg)


if __name__ == "__main__":
    main()
