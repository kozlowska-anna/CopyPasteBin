# Architektura CopyPasteBin V1

## Źródło prawdy

Aktualnym interfejsem pulpitu jest lekkie rozszerzenie GNOME Shell 50 w
`gnome-extension/copypastebin@kozlowska-anna.github.io`. Pollingowy watcher
`wl-paste`, jego usługa systemd oraz dawny launcher są kodem legacy i nie
należą do codziennej ścieżki GNOME.

```text
GNOME Meta.Selection owner-changed
  -> bramka blokady ekranu i pauzy
  -> ograniczony transfer tekstowego MIME
  -> anonimowy stdin do `cpb bridge observe`
  -> lokalny silnik reguł i historia metadanych
  -> ograniczony JSON ryzyka/kategorii
  -> lokalny baner St bez treści schowka
```

## Moduły rdzenia

- `input_sources.py` — ograniczony odczyt UTF-8 z jawnego źródła;
- `detection.py` — biblioteka sekretów dostawców, JWT i URI baz danych,
  reguły danych osobowych, rozstrzyganie nakładania i checksum BIP-39;
- `data/bip39_english.txt` — wersjonowana lokalna lista 2048 słów;
- `models.py` — niemutowalne modele z redagowanym `repr`;
- `safe_text.py` — neutralizacja prezentacji terminalowej;
- `history.py` — prywatny magazyn SQLite oraz HMAC;
- `application.py` — analiza i zapis metadanych operacji;
- `application_id.py` — zamknięta normalizacja identyfikatora aplikacji;
- `pause.py` — prywatny, trwały stan pauzy bez danych schowka;
- `filters.py` — prywatny stan włączonych kategorii wykrywania;
- `language.py` — prywatny wybór języka GUI: systemowy, polski lub angielski;
- `bridge.py` — ograniczony most zdarzenia GNOME przez stdin;
- `ui.py` — ograniczone JSON-y historii, filtrów, reguł i pozycji detekcji
  oraz sugestia anonimizacji;
- `cli.py` — jawne CLI oraz zamknięte protokoły wewnętrzne.

Moduły legacy:

- `clipboard.py` — jawny adapter `wl-paste`/`wl-copy` dla CLI;
- `watcher.py` — odrzucony dla GNOME pollingowy watcher foreground;
- `lifecycle.py` — preflight i blokada starego watchera;
- `service.py` — kontroler dawnej usługi `systemd --user`;
- `launcher.py` — instalator dawnego launchera usługi;
- `notifications.py` — beztreściowa notyfikacja starego watchera;
- `executables.py` — walidacja entry pointu używana przez legacy lifecycle.

Kod legacy pozostaje pokryty testami, ale nie może być uruchamiany równolegle
z rozszerzeniem i nie powinien być instalowany jako produkt GNOME.

## Rozszerzenie GNOME

`extension.js` subskrybuje wyłącznie zmianę
`Meta.SelectionType.SELECTION_CLIPBOARD`. Nie ma timera odczytu ani globalnego
hooka klawiatury. Timer minutowy służy wyłącznie odświeżaniu widocznego licznika
pauzy.

Jedynym skrótem rozszerzenia jest `safe-paste` z własnego schematu GSettings,
domyślnie `Super+Shift+V`. Rejestracja używa `Main.wm.addKeybinding` w
`Shell.ActionMode.NORMAL`, a wyłączenie symetrycznie wywołuje
`removeKeybinding`. Jest to jawna akcja, nie globalny hook: nie przechwytuje
`Ctrl+V`, nie emuluje wklejenia i nie obserwuje innych klawiszy.

Przed transferem rozszerzenie:

1. odrzuca zdarzenie podczas blokady albo na ekranie logowania;
2. pyta rdzeń o stan pauzy;
3. wybiera MIME z zamkniętej listy tekstowej;
4. pobiera najwyżej 10 MiB + 1 bajt;
5. normalizuje źródło bez tytułu okna, PID i ścieżki procesu;
6. przekazuje ramkę przez stdin do stałego `cpb bridge observe`.

Ramka zawiera długość ograniczonego identyfikatora aplikacji, identyfikator
ASCII oraz tekst UTF-8. Tekst nie trafia do argv, env, pliku tymczasowego ani
logu. Most ponownie sprawdza pauzę bezpośrednio przed analizą.

Odpowiedź mostu ma najwyżej 2 KiB i zamknięty schemat: wersja, poziom oraz
pary kategoria–licznik. Nie zawiera treści, redakcji, pozycji dopasowań ani ID
operacji. Rozszerzenie waliduje cały dokument przed użyciem.

## Historia metadanych i ostatnie wpisy w RAM

`HistoryStore` nadal zapisuje wyłącznie metadane, techniczny HMAC i relację
duplikatu. Nigdy nie zapisuje oryginału, zanonimizowanego tekstu ani fragmentu;
retencja wynosi 90 dni i 1000 rekordów. Cel zwykłego kopiowania pozostaje
`unknown`, bo zmiana fokusu nie dowodzi wklejenia.

Do codziennego UX rozszerzenie utrzymuje osobny stan RAM: do 15 tekstów,
256 KiB na wpis i 2 MiB łącznie. Stan należy do obiektu rozszerzenia, dzięki
czemu przełączenie języka nie usuwa listy; `disable()` zwalnia wpisy. Brak
trybu `unlock-dialog` w `metadata.json` powoduje standardowe wyłączenie
rozszerzenia przy blokadzie ekranu, więc odblokowanie rozpoczyna pustą listę.
Menu pokazuje tylko licznik i otwiera na żądanie `recent-clipboard.js`.

Okno otrzymuje przez stdin ograniczoną binarną migawkę z identyfikatorem,
czasem i tekstem. Podgląd neutralizuje znaki sterujące i bidi. stdout zwraca
wyłącznie pięć bajtów: zamkniętą akcję oraz identyfikator wpisu, nigdy treść.
Nowe kopiowania podczas otwartego okna nie zmieniają jego migawki; wpis
usunięty w międzyczasie nie może zostać przywrócony.

## Pauza jako granica prywatności

`pause.py` obsługuje dokładnie 30 minut, 1 godzinę, tryb bezterminowy i jawne
wznowienie. Atomowy plik `0600` w katalogu `0700` zawiera tylko wersję, tryb
i opcjonalny termin Unix. Symlinki, obcy właściciel, złe prawa, nadmiarowe pola
i uszkodzenie są odrzucane fail-closed.

Pauza nie jest wyciszeniem notyfikacji. Rozszerzenie nie żąda w tym czasie
treści i nie tworzy wpisu. Po wznowieniu wartość zastana w schowku jest
pomijanym punktem odniesienia; analizowane jest dopiero kolejne kopiowanie.

## Ustawienia filtrów

`filters.py` przechowuje wersję, posortowaną listę wyłączonych wartości
`Category` i zamknięte ustawienie czyszczenia 0/60/300/900 sekund w atomowym
pliku `0600`. Brak pliku oznacza wszystkie
filtry włączone. Nieznana kategoria, duplikat, rozszerzony dokument, symlink,
obcy właściciel albo złe prawa są odrzucane fail-closed.

Rozszerzenie pobiera zamknięty JSON przez `cpb ui filters` i zmienia dokładnie
jedną kategorię przez `cpb ui filter-set <CATEGORY> on|off`. Główne menu pokazuje
tylko sumę aktywnych filtrów. Kliknięcie uruchamia na żądanie `filter-editor.js`:
osobne przewijane okno 17 pól wyboru, które zapisuje każdą zmianę od razu.
Odpowiedź ma limit 2 KiB i ustaloną kolejność wszystkich kategorii.

Wyłączone kategorie są usuwane przed rozstrzygnięciem nakładania detekcji.
Nie wywołują ostrzeżenia, nie trafiają do kategorii nowego wpisu i nie są
zastępowane przez sugestię anonimizacji. Ustawienie działa również dla jawnej
analizy CLI. Nie modyfikuje wpisów historycznych i nie zastępuje pełnej pauzy:
backend nadal obserwuje zdarzenie, ale ignoruje wyłączony rodzaj dopasowania.

## Język interfejsu

Angielski tekst jest bazowym katalogiem GUI w `i18n.js`, a polskie napisy są
wbudowanym tłumaczeniem. Rozszerzenie pobiera wyłącznie zamknięty dokument
`{version, choice, effective}` przez `cpb ui language` i zapisuje jedną z
wartości `system`, `pl`, `en` przez `cpb ui language-set`. Po zmianie odtwarza
wskaźnik, aby wszystkie elementy menu i banera miały jeden język. Osobne
procesy GTK otrzymują tylko zamknięty argument `--language=pl|en`; tekst
schowka nadal przechodzi wyłącznie przez stdin.

`language.py` zapisuje wybór atomowo w `language.json` jako plik `0600` w
katalogu stanu `0700`. Brak pliku oznacza język systemu. Uszkodzony dokument,
symlink, obcy właściciel albo niewłaściwe prawa są odrzucane, a odpowiedź
błędu nie ujawnia ścieżki ani treści.

Pozycja „Reguły własne i wykluczenia” uruchamia na żądanie osobny proces GTK
`rules-editor.js`. Odczyt używa `cpb ui rules`, a atomowy zapis ograniczonego
JSON-u — `cpb ui rules-save` przez stdin. Najwyżej 32 dosłowne reguły i 32
dosłowne wykluczenia trafiają do prywatnego `config.toml`; każdy wpis ma trwałe
pole `enabled`, dzięki któremu może zostać wyłączony bez usuwania. Konfiguracja
V1 zawierająca tylko reguły jest odczytywana i przy następnym zapisie migrowana
do V2. Proces jest kończony podczas wyłączenia rozszerzenia.

Okno ma jeden stały widok z dwiema równoległymi kolumnami: regułami własnymi i
wykluczeniami. Każda kolumna pokazuje bez zwijania osobne listy aktywnych i
nieaktywnych wpisów wraz z licznikami. Zmiana checkboxa przenosi wiersz między
tymi listami; nie jest potrzebny kolor ani dodatkowa etykieta rodzaju wpisu.

Aktywne wykluczenie tworzy zakresy dokładnych, uwzględniających wielkość liter
wystąpień literału. Usuwana jest tylko detekcja o identycznym początku i końcu;
częściowa zgodność nie ukrywa szerszej detekcji, a trafienia sąsiadujące
pozostają aktywne. Wykluczenie nie jest kategorią, nie trafia do historii i nie
powoduje anonimizacji. Interfejs jawnie ostrzega, że nie należy wpisywać do
wykluczeń prawdziwych danych wrażliwych.

Dla pojedynczego trafienia `low` lub `medium` banner może uruchomić ograniczone
`ui detections` na tej samej treści przekazanej przez stdin. Rozszerzenie
waliduje zamknięty JSON pozycji, lokalnie wycina dokładny zakres i przekazuje
go stdin do istniejącego edytora reguł. Edytor dodaje wartość wyłącznie do
formularza; dopiero „Zapisz” aktualizuje `config.toml`. Ścieżka jest wyłączona
dla `high`, `critical`, wielu różnych wartości, znaków sterujących, zakresów poza 3–128
znaków oraz tekstów większych niż 256 KiB.

Listy 20 walut tradycyjnych i 20 kryptowalut są stałymi skompilowanymi raz z
modułem detekcji. Nie ma procesu aktualizującego, sieci ani osobnego skanowania
w tle; koszt pozostaje częścią pojedynczej analizy po zdarzeniu.

PESEL, IBAN i karta płatnicza są najpierw wyłapywane przez ograniczone wzorce
kandydatów, a następnie lokalnie walidowane odpowiednio przez checksum z datą,
modulo 97 i Luhna. Nie ma zapytania do rejestru, banku ani operatora karty.
Klucz odzyskiwania BitLocker jest kandydatem 48-cyfrowym w ośmiu grupach;
każda grupa przechodzi lokalną kontrolę zakresu i podzielności przez 11. Jego
pełny zakres jest wyłączony z heurystyki telefonu także wtedy, gdy użytkownik
wyłączy filtr klucza odzyskiwania.
Osobna reguła kontekstowa mapuje inne ciągi do tej samej kategorii wyłącznie po
etykiecie recovery key/code/password albo „klucz odzyskiwania”. Pozwala to
rozszerzać kategorię poza BitLocker bez szerokiej heurystyki długości.

Przed uruchomieniem heurystyki telefonu silnik wyszukuje ograniczone kandydaty
dat `YYYY-MM-DD` i `DD-MM-YYYY`, również z kropką lub ukośnikiem, i sprawdza je
przez lokalny kalendarz. Tylko zakresy poprawnych dat są maskowane w kopii
tekstu używanej przez regułę telefonu. Pozycje pozostają zgodne z oryginałem,
a numer telefonu obok daty nie jest pomijany. Niepoprawny kandydat daty nie
uzyskuje wyjątku.

Po maskowaniu dat silnik wyznacza maksymalne ciągi cyfr połączonych spacją,
kropką, myślnikiem lub nawiasem. Cały kandydat musi mieć 7–15 cyfr i przejść
walidację separatorów, nawiasów, grupowania oraz ograniczonego kontekstu.
Odrzucenie dotyczy całego ciągu, dlatego długi identyfikator nie rozpada się na
kilka dopasowań telefonu. Etykiety identyfikatorów są sygnałem ujemnym tylko
dla niejednoznacznej struktury; `+`, nawias lub etykieta telefonu są sygnałami
silnymi. Analiza pozostaje lokalna i nie odpytuje operatorów ani rejestrów.
Jeżeli cały ciąg przekracza limit 15 cyfr, walidator sprawdza jego niespacyjne
fragmenty tylko przy dodatnim kontekście telefonu albo gdy fragment ma własne
formatowanie. Ujemny kontekst identyfikatora obejmuje cały ciąg i wyłącza ten
drugi przebieg. Nieopisane zwarte pola liczbowe rozdzielone samą spacją
pozostają nierozstrzygnięte i nie są dzielone na arbitralne okna.

Podmenu automatycznego czyszczenia korzysta z `cpb ui auto-clear` i
`auto-clear-set`. Rozszerzenie uruchamia timer dopiero po ostrzeżeniu, wiąże go
z numerem zdarzenia i anuluje przy każdym kolejnym owner-change, edycji, pauzie
albo wyłączeniu. Przed ustawieniem pustego tekstu ponownie sprawdza pauzę.

## Baner i wskaźnik

Ostrzeżenia są renderowane lokalnie jako aktor `St`:

- `low` — niebieski;
- `medium` — bursztynowy;
- `high` — czerwony;
- `critical` — ciemnoczerwony;
- `success` — zielony;
- informacje techniczne — niebieskie.

Baner zawiera tylko bezpieczne kategorie i liczniki. Ma akcję „Edytuj”, ręczne
zamknięcie i czas życia 6 sekund. Kolejne zdarzenie zastępuje poprzedni baner.
Blokada ekranu ukrywa go natychmiast. Pozycja jest liczona względem ikony oraz
granic głównego monitora: pod panelem górnym albo nad dolnym.

Tekstowy MIME o długości zero jest stanem informacyjnym, nie awarią ochrony.
Pozostaje widoczny jako niebieski baner „pusty schowek”, nie trafia do mostu ani
historii i nie zmienia zielonego stanu ochrony. Błędy transferu oraz nadmiar
pozostają czerwone i fail-closed.

GNOME Shell 50.1 nie akceptuje parametru `affectsInputRegion` w użytym
`Main.layoutManager.addChrome`; nie wolno go dodawać. Wyłączenie rozszerzenia
usuwa aktor, timer oraz sygnał trybu sesji.

Ikona korzysta z trzech lokalnych SVG. Zielona tylna kartka pojawia się tylko
po dokładnie potwierdzonym `ACTIVE`; pauza, przejście i błąd używają czerwieni
fail-closed.
Wariant kopiowania zachowuje zieloną tylną kartkę, ale przez 200 ms
zmienia czarną przednią kartkę na `#E8E8E8`, gdy aktywny backend zauważy zmianę
właściciela schowka. Timer jest odnawiany przez kolejne kopiowanie, anulowany
przez stan nieaktywny i usuwany w `destroy()`. Nie wpływa na banery.

## Edytor

`editor.js` jest osobnym procesem GTK uruchamianym wyłącznie na żądanie.
Oryginał trafia stdin, a zatwierdzony wynik wraca stdout. Rozszerzenie pozostaje
właścicielem jawnego zapisu schowka i ignoruje własne zdarzenie zmiany.

Anonimizacja korzysta z `cpb ui redact` przez ten sam prywatny kanał. Edytor
oferuje lokalne poprawianie tekstu, znajdź/zamień, cofanie do 50 kroków oraz
potwierdzane czyszczenie. Narzędzia nie są ładowane w ścieżce zwykłego
kopiowania. Pauza jest ponownie sprawdzana przed otwarciem, sugestią i zapisem.
Użytkowniczka może wysłać do tego kanału cały tekst albo tylko zaznaczony
fragment. W drugim trybie edytor zachowuje pozycje i wersję bufora, a wynik
podstawia tylko wtedy, gdy tekst nie zmienił się w trakcie analizy. Podstawienie
zaznaczenia jest pojedynczą operacją cofania i nie dotyka innych trafień.
`cpb ui detections` zwraca do 1000 niepokrywających się pozycji, kategorii
i poziomów bez treści. Edytor oznacza je kolorami, a każda zmiana tekstu usuwa
stare znaczniki.
Znaczniki są obiektami GTK4 `TextTag` dodanymi do `TextTagTable`. Rozszerzenie
wiąże stan „otwarty” z konkretnym procesem, czyści referencję w każdej ścieżce
zakończenia i może przywrócić jego okno stałym lokalnym sygnałem bez treści.

Tryb bezpiecznego wklejenia wywołuje `ui detections` na żądanie. `none` kończy
się lokalnym potwierdzeniem bez zmiany danych. Dla pozostałych poziomów
rozszerzenie otwiera ten sam edytor z flagą stałą `--suggest-redaction`; tekst
nadal idzie wyłącznie stdin, a edytor automatycznie przygotowuje propozycję w
buforze. Zapis do schowka nadal wymaga kliknięcia. `high` i `critical` pokazują
dodatkowy komunikat wysokiego ryzyka, bez ścieżki trwałego wyjątku.

## Wyjście i launcher

„Wyjdź z CopyPasteBin” wymaga drugiego kliknięcia w ciągu 8 sekund. Wywołuje
stałe `/usr/bin/gnome-extensions disable <własny UUID>` bez shella i przechodzi
przez normalne `disable()`, które sprząta transfery, sygnały, edytor, baner i
timery.

Aktualny `packaging/copypastebin.desktop` wykonuje wyłącznie odwrotne
`gnome-extensions enable copypastebin@kozlowska-anna.github.io`. Nie uruchamia
terminala, starej usługi ani `watch start`.

Pięć osobnych procesów GTK ma stabilne identyfikatory aplikacji dla edytora,
filtrów, reguł, ostatnich wpisów i okna „O programie”. Paczka instaluje dla
nich ukryte (`NoDisplay=true`) pliki desktop o nazwach zgodnych z tymi
identyfikatorami. Wszystkie wskazują lokalną ikonę `copypastebin`, dzięki czemu
GNOME/Wayland przypisuje otwarte okna do ikony produktu zamiast ogólnej ikony
ustawień. Wpisy nie dodają kolejnych pozycji do menu aplikacji.

Pełnowymiarowa ikona produktu jest osobnym skalowalnym zasobem
`packaging/copypastebin-app.svg`. Zachowuje metaforę dwóch dokumentów, zieleń,
grafitowy przód i jasne linie z małej ikony panelu. Nie ma kafla ani tła:
dwie kartki mają przeciwne, lekkie obroty, własne linie tekstu, gradienty,
jasną krawędź i zwarte cienie, dzięki którym kształt pozostaje ostry również
na ciemnym tle siatki aplikacji oraz przełącznika okien. Ikony stanu
rozszerzenia pozostają niezależnymi zasobami 18 px, zoptymalizowanymi dla
panelu; builder nie skaluje już `icon-active.svg` jako ikony aplikacji.

## CLI i analiza jawna

Rdzeń może analizować dokładnie jedno jawne źródło: stdin, zwykły plik UTF-8
albo jednorazowy schowek. `--copy redacted` zapisuje anonimizację, a
`--copy original` podlega polityce ryzyka. Oryginał wysokiego ryzyka wymaga
jednorazowego `COPY <operation_id>` w bieżącym procesie.

## Legacy watcher

Pollingowy `WlPastePollingBackend` ma zamknięty, fail-closed kontrakt oraz
ograniczony startup grace 1/2/4/8 s, ale live test GNOME Shell 50.1 wykazał
kradzież fokusu przez tymczasową powierzchnię Wayland. Z tego powodu:

- stara usługa i dawny launcher mają pozostać nieaktywne;
- nie zwiększamy interwału ani liczby prób;
- nie parsujemy stderr i nie zgadujemy po exit code;
- nie traktujemy legacy lifecycle jako alternatywnej ścieżki produktu.

Powód wyłączenia tej architektury jest opisany powyżej, a jej zamknięty
kontrakt pozostaje pokryty testami.

## Granice produktu

Brak sieci, chmury, globalnego `Ctrl+V`, auto-paste, auto-send, OCR, obsługi
plików binarnych i gwarancji wykrycia wszystkich sekretów. Automatyczna zmiana
każdego kopiowania w tle jest poza kontraktem; edycja i anonimizacja pozostają
jawne.
