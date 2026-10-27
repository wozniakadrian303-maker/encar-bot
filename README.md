# Bot Encar → Telegram

Co ~15 minut sprawdza Twoje wyszukiwanie na Encar (Kia Stinger Meister 3.3 GT, 2WD i AWD) i wysyła na Telegram:
- 🆕 każde nowe ogłoszenie (zdjęcie, cena, rok, przebieg, miasto, link),
- 📉 obniżki cen aut, które już widział.

Przy pierwszym uruchomieniu bot tylko zapamiętuje obecne ogłoszenia i wysyła jedną wiadomość „Bot uruchomiony”, żeby Cię nie zasypać.

---

## Krok 1. Bot na Telegramie

1. Na Telegramie napisz do **@BotFather** → `/newbot` → podaj nazwę → zapisz **token**.
2. Otwórz swojego nowego bota i napisz do niego cokolwiek, np. „hej”.
3. Wejdź w przeglądarce na adres (wstaw swój token):
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
   Znajdź `"chat":{"id":123456789` – ta liczba to Twój **chat_id**.

## Krok 2. GitHub (darmowy serwer)

1. Na github.com kliknij **New repository**, nazwa np. `encar-bot`, ustaw **Public** (publiczne repo ma nielimitowane darmowe minuty; token i tak jest ukryty w sekretach).
2. **Add file → Upload files** i wrzuć zawartość tego folderu **razem z folderem `.github`** (jeśli przeglądarka go nie pokazuje, utwórz plik ręcznie: **Add file → Create new file**, nazwa `.github/workflows/encar.yml`, wklej treść).
3. **Settings → Secrets and variables → Actions → New repository secret**, dodaj dwa sekrety:
   - `TELEGRAM_TOKEN` – token z kroku 1,
   - `TELEGRAM_CHAT_ID` – chat_id z kroku 1.
4. Zakładka **Actions** → **Encar bot** → **Run workflow**.

Po minucie powinna przyjść wiadomość „✅ Bot uruchomiony”. Od tej pory bot działa sam.

### Jeśli zamiast wiadomości jest czerwony ❌ i błąd typu „403”, „timed out” albo „Nie udało się pobrać danych z Encar”

Encar blokuje część serwerów w chmurze. Wtedy użyj kroku 3: bot działa identycznie, tylko z Twojego internetu. W GitHubie wyłącz wtedy workflow (Actions → Encar bot → ⋯ → Disable workflow).

## Krok 3 (zapasowy). Komputer albo stary telefon z Androidem

Potrzebny jest Python 3 (bez dodatkowych paczek).

**Komputer (Windows/Mac/Linux):**
1. Zainstaluj Pythona z python.org (na Windows zaznacz „Add Python to PATH”).
2. Skopiuj `config.env.example` jako `config.env` i wpisz token oraz chat_id.
3. W folderze bota uruchom:
   ```
   python bot.py --test        # testowa wiadomość na Telegram
   python bot.py --loop 600    # sprawdzanie co 10 minut
   ```
   Bot działa, dopóki okno jest otwarte, a komputer nie śpi.

**Stary telefon z Androidem (najlepsza opcja na 24/7, prawie zero prądu):**
1. Zainstaluj **Termux** z F-Droid.
2. W Termuxie: `pkg install python`, a potem przenieś folder bota (np. `termux-setup-storage` i skopiuj z Pobranych).
3. Uzupełnij `config.env` i uruchom `python bot.py --loop 600`.
4. W ustawieniach Androida wyłącz oszczędzanie baterii dla Termuxa i zostaw telefon na ładowarce.

## Zmiana wyszukiwania

Ustaw filtry na car.encar.com, skopiuj link z paska adresu i:
- na GitHubie: **Settings → Secrets and variables → Actions → zakładka Variables → New variable**, nazwa `SEARCH_URL`, wartość = link,
- lokalnie: wklej link do `SEARCH_URL=` w `config.env`.

Po zmianie linku bot zacznie od nowa (znów jedna wiadomość „Bot uruchomiony”).

## Przydatne

- `python bot.py --chat-id` pokazuje Twój chat_id (po napisaniu czegoś do bota).
- Ceny na Encar są w 만원 (1 만원 = 10 000 KRW). Bot pokazuje obie wartości.
- Plik `seen.json` to pamięć bota. Jego usunięcie = start od zera.
