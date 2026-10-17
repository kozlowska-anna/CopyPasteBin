# Zdarzeniowy backend GNOME — aktualny kontrakt

## Cel

Sekundowy polling `wl-paste` został zastąpiony komponentem dla GNOME Shell 50,
który reaguje na zmianę schowka bez tworzenia powierzchni Wayland i bez
zakłócania fokusu. Backend działa jako rozszerzenie GNOME i wewnętrzny most
stdin do rdzenia Pythona. Stary watcher pozostaje osobnym kodem legacy, ale
nie może być uruchamiany równolegle ani używany w codziennej sesji GNOME.

## Minimalny podział odpowiedzialności

Komponent GNOME Shell:

- subskrybuje wyłącznie `Meta.Selection::owner-changed` dla
  `Meta.SelectionType.SELECTION_CLIPBOARD`;
- nie używa timera ani pollingu;
- przed żądaniem treści pyta rdzeń CPB o stan pełnej pauzy;
- przy aktywnej ochronie wybiera tekstowy MIME z zamkniętej listy i pobiera
  najwyżej 10 MiB + 1 bajt przez `Meta.Selection.transfer_async`;
- po transferze porównuje wyłącznie ulotny skrót SHA-256 z ostatnią obsłużoną
  lub właśnie analizowaną treścią; identyczne techniczne przekazanie własności
  nie tworzy nowego zdarzenia, nie resetuje timera i nie trafia ponownie do
  mostu;
- pobiera stabilny identyfikator aplikacji z okna mającego fokus w chwili
  zdarzenia, bez tytułu okna, nazwy dokumentu, adresu strony i PID;
- nie analizuje, nie redaguje, nie zapisuje historii i nie loguje treści;
- po wyłączeniu anuluje transfery i odłącza wszystkie sygnały.

Osobna jawna akcja `Super+Shift+V` jest jednym keybindingiem GNOME, nie częścią
subskrypcji `owner-changed`. Sprawdza lock/greeter i pauzę, pobiera tekst tylko
po naciśnięciu, wywołuje `ui detections` przez stdin i nie generuje zdarzenia
wklejenia. `Super+V` pozostaje przypisany do zasobnika wiadomości GNOME;
zwykły `Ctrl+V` nie jest przechwytywany.

Rdzeń CopyPasteBin:

- jest jedynym właścicielem stanu pauzy i silnika detekcji;
- odpowiada komponentowi GNOME, czy wolno pobrać treść danego zdarzenia;
- przyjmuje tekst strumieniowo, bez argv, env i pliku tymczasowego;
- zapisuje najwyżej 8 wpisów metadanych, bez treści;
- oznacza zwykłe wklejenie celem `unknown`;
- zwraca rozszerzeniu wyłącznie ograniczone metadane poziomu i kategorii;
- nie modyfikuje schowka bez jawnej akcji użytkownika albo wcześniej
  wybranej opcji czasowego czyszczenia ostrzegającego wpisu.

Komunikacja między komponentami używa anonimowego stdin procesu uruchamianego
ze stałym argv `cpb bridge observe`. Krótka ramka zawiera wyłącznie ograniczony
identyfikator aplikacji oraz treść UTF-8. Treść nie znajduje się w argv, env,
pliku tymczasowym, logu ani publicznym komunikacie. Most odrzuca niepełne,
nadmiarowe i niepoprawne ramki oraz ponownie sprawdza pauzę przed analizą.
Odpowiedź stdout ma najwyżej 2 KiB i zawiera jedynie wersję, poziom oraz
zamknięte pary kategoria–licznik. Rozszerzenie waliduje ją przed pokazaniem
własnego kolorowego banera pod ikoną. Nie używa systemowego `notify-send` dla
tej ścieżki, nie umieszcza treści w banerze i ukrywa go przy blokadzie ekranu.

Osobny zamknięty protokół `ui filters` / `ui filter-set` obsługuje lekkie,
przewijane okno ustawień 17 kategorii. Główne menu pokazuje tylko licznik.
Protokół zwraca pełną listę boolean do 2 KiB i zapisuje tylko
nazwy kategorii, bez treści. Wyłączona kategoria jest usuwana przed wyborem
detekcji, więc nie ostrzega, nie trafia do licznika historii i nie jest
anonimizowana; inne kategorie w tym samym tekście pozostają aktywne.
Każda zmiana ptaszka jest zapisywana od razu, a proces okna kończy się przy
wyłączeniu rozszerzenia.

Zarządzanie regułami własnymi jest oddzielnym procesem GTK uruchamianym tylko
po kliknięciu. Używa zamkniętych poleceń `ui rules` i `ui rules-save`, limitu
32 reguł, 32 dosłowne wykluczenia, flagi aktywności oraz 64 KiB JSON. Zapis przechodzi stdin bez shella, a zamknięcie lub
wyłączenie rozszerzenia kończy proces pomocniczy.

Przycisk „Nie ostrzegaj ponownie” istnieje tylko na bannerze `low` lub `medium`.
Na żądanie pobiera przez `ui detections` ograniczone pozycje, wybiera dokładną
wartość tylko przy jednym jednoznacznym kandydacie i przekazuje ją stdin do
edytora reguł. Edytor nie zapisuje jej automatycznie: pokazuje propozycję i
wymaga kliknięcia „Zapisz”. `high`, `critical`, wiele różnych wartości i tekst ponad
256 KiB nie korzystają z tej ścieżki.

`ui auto-clear` / `ui auto-clear-set` udostępnia zamknięte opcje 0, 60, 300
i 900 sekund. Timer powstaje wyłącznie po ostrzeżeniu i jest związany z numerem
zdarzenia, więc nowe kopiowanie, edycja, pauza lub wyłączenie go anuluje.
`ui detections` zwraca edytorowi wyłącznie pozycje, kategorie i poziomy ryzyka,
bez dopasowanego tekstu.

## Tożsamość aplikacji

Do historii trafia jeden z zamkniętych wyników:

1. identyfikator aplikacji sandboxowej, jeżeli istnieje;
2. identyfikator aplikacji GTK;
3. identyfikator aplikacji GNOME Shell skojarzonej z oknem;
4. bezpiecznie znormalizowane `wm-class` jako ostateczny fallback;
5. `unknown`.

Nie zapisujemy tytułu okna, opisu okna, PID, ścieżki wykonywalnej ani dowolnej
wartości dostarczonej przez aplikację bez ograniczenia długości i alfabetu.
Zmiana fokusu po kopiowaniu nie uzupełnia celu.

## Pauza

Pauza jest sprawdzana przed transferem selection. W trybie 30 minut, 1 godziny
lub bezterminowym komponent GNOME nie żąda MIME ani treści i nie tworzy
zdarzenia historii. Po wygaśnięciu terminu rdzeń oznacza pierwszy zastany
owner-change jako punkt odniesienia do pominięcia. Dopiero następna zmiana może
być analizowana. Wznowienie generuje neutralne powiadomienie bez identyfikatora
aplikacji i danych schowka.

## Kryteria żywej sesji

1. Menu kontekstowe pozostaje otwarte przez co najmniej 30 sekund.
2. Nie istnieje proces `wl-paste` ani timer odczytu schowka.
3. Jedno kopiowanie daje najwyżej jeden wpis historii.
4. Pauza powoduje zero żądań transferu treści.
5. Wartość zastana po wznowieniu nie jest analizowana wstecz.
6. Historia ma najwyżej 8 wpisów i nie zawiera treści ani tytułów okien.
7. Wyłączenie komponentu usuwa sygnały, anuluje transfer i nie pozostawia
   procesu pomocniczego.
8. Awaria kanału, nieznany MIME, nadmiar, zły UTF-8 i błąd transferu kończą
   dane zdarzenie fail-closed, bez fałszywego wpisu sukcesu.
9. Blokada ekranu nie powoduje odczytu schowka; zachowanie po odblokowaniu jest
   takie samo jak po wznowieniu z pauzy.
10. Treść testowego canary nie pojawia się w journalu, historii, błędach,
    repr, argv, env ani plikach stanu.
11. `Super+Shift+V` nie zmienia schowka dla `none` ani po anulowaniu edytora,
    a wyłączenie rozszerzenia usuwa skrót i kończy aktywną kontrolę.
12. Techniczna zmiana właściciela z identyczną treścią nie tworzy drugiego
    bannera, wpisu historii ani wpisu listy ostatnich i nie przesuwa czasu
    automatycznego czyszczenia; jawne Bezpieczne wklejenie nadal analizuje ją
    na żądanie.

Stan 2026-09-21: punkty 1–6 przeszły live test, w tym stabilne menu
kontekstowe, ostrzeżenia, historia, pauza, brak analizy wstecz i ponowne
wykrywanie dopiero następnego kopiowania. Jawne „Wyjdź” przeszło live test
normalnej ścieżki `disable()`, a punkt 10 pokrywa automatyczny canary. Osobnej
próby nadal wymaga zachowanie transferu podczas blokady/odblokowania oraz
wyłączenie dokładnie w trakcie dużego aktywnego transferu.

## Poza prototypem

- zgadywanie celu zwykłego `Ctrl+V`;
- globalny hook klawiatury;
- przechowywanie treści historii;
- obsługa obrazów i plików;
- automatyczne redagowanie albo przekształcanie każdego kopiowania w tle;
- synchronizacja sieciowa;
- zgodność z desktopami innymi niż GNOME.
