# Obsługa sekretów i bezpieczeństwo historii schowka

**Data badania:** 4 listopada 2026
**Zakres kodu:** CopyPasteBin 1.2, gałąź `codex/cpb-1.2-distribution`, punkt
wyjścia `f3caf58`
**Charakter dokumentu:** audyt techniczny i rejestr wiedzy; nie jest zgodą na
rozszerzanie uprawnień ani wdrażanie obsługi metadanych schowka.

## Sposób rozróżniania dowodów

- **Potwierdzone w kodzie CPB** — wynik przeglądu aktualnego drzewa 1.2.
- **Potwierdzone testem automatycznym** — test na danych syntetycznych.
- **Potwierdzone w kodzie lub dokumentacji źródła** — zachowanie zewnętrznego
  projektu, które może zależeć od jego wersji i ścieżki uruchomienia.
- **Niewykonany test LIVE** — wymaga konkretnej aplikacji i sesji GNOME 50 /
  Wayland. Brak takiego testu nie jest ani potwierdzeniem błędu, ani dowodem
  poprawnego działania.

Nie odczytywano prawdziwego schowka, historii ani danych logowania. Próby
automatyczne korzystały wyłącznie z wartości syntetycznych.

## Najważniejsze wnioski

1. CPB 1.2 potrafi pobrać listę formatów oferowanych przez właściciela
   schowka, lecz wybiera z niej wyłącznie `text/plain;charset=utf-8` albo
   `text/plain`. Nie sprawdza `x-kde-passwordManagerHint` i nie odczytuje jego
   wartości.
2. Python nie ma bezpośredniego dostępu do systemowego schowka w aktualnej
   ścieżce GNOME. Dostaje od rozszerzenia jedynie ograniczony identyfikator
   aplikacji i tekst. Znacznik utracony po stronie rozszerzenia nie może zostać
   odzyskany przez `bridge.py`.
3. Samą nazwę formatu można zobaczyć przed pobraniem tekstu. Nie dowodzi ona
   jednak, że wartość znacznika jest równa `secret`; do wiarygodnej decyzji
   potrzebny jest osobny, ograniczony transfer i ścisła walidacja wartości.
4. GNOME Shell używa `Meta.Selection`, a nie GTK 4, więc rozszerzenie ma
   techniczną możliwość poproszenia o dodatkowy oferowany format bez nowych
   uprawnień. Dostępność formatu zależy jednak od aplikacji źródłowej i drogi
   przez Wayland, XWayland lub portal. Wymaga to osobnych testów LIVE.
5. Obecna podstawowa ochrona historii jest prawidłowo oddzielona od filtrów
   ostrzeżeń: pełne detekcje trafiają najpierw do `history_policy.py`, a dopiero
   potem filtry wpływają na banner i metadane widoczne użytkowniczce.
6. Potwierdzono lukę w pomocniczej heurystyce historii: dowolne `@` wyłączało
   ocenę entropii. W ramach tego zadania zawężono wyjątek do tekstu
   rozpoznanego w całości jako adres e-mail i dodano testy regresyjne. Nie
   zmieniono detektorów, filtrów, uprawnień ani architektury.
7. Znacznik i analiza treści są niezależnymi warstwami. Część źródeł nie
   przekazuje znacznika, a część haseł nie spełni reguł tekstowych. Brak
   znacznika nigdy nie oznacza, że treść jest bezpieczna.

## Aktualny przepływ danych w CPB 1.2

### GNOME Shell

`extension.js::_onOwnerChanged()` reaguje na
`Meta.SelectionType.SELECTION_CLIPBOARD::owner-changed`. Po sprawdzeniu blokady
ekranu i Pauzy wywołuje `_transferText()`.

`_transferText()`:

1. pobiera `this._selection.get_mimetypes(...)`;
2. wybiera pierwszy z dwóch zamkniętych formatów tekstowych;
3. pobiera do 10 MiB + 1 bajt kontrolny przez `transfer_async()`;
4. przekazuje do workera identyfikator aplikacji i bajty tekstu.

Lista formatów jest więc dostępna przed transferem tekstu. Aktualny kod nie
przechowuje jej, nie wysyła do Pythona i nie sprawdza żadnego znacznika
sekretu.

### Most i polityka historii

`bridge.py::observe_framed_event()` wykonuje kolejno:

1. ponowne sprawdzenie Pauzy;
2. walidację ramki i tekstu;
3. `detect_text()` bez filtrów użytkownika;
4. `history_text_is_eligible(text, detections)` z pełnej listy detekcji;
5. osobne zastosowanie filtrów i wykluczeń do wyniku ostrzeżenia;
6. zapis technicznych metadanych operacji;
7. zwrot zamkniętego JSON z `history_eligible`.

Po stronie rozszerzenia `_sendToBridge()` dodaje tekst do listy RAM wyłącznie,
gdy odpowiedź jest poprawna i `history_eligible` ma wartość `true`.
`_rememberRecentClipboard()` ponownie sprawdza ustawienie zapisywania historii
oraz limity wpisu i całej listy.

## Znacznik `x-kde-passwordManagerHint`

### Co oznacza

CopyQ opisuje konwencję linuksową jako format
`x-kde-passwordManagerHint` o wartości `secret`. Gdy oba warunki są spełnione,
CopyQ domyślnie nie zapisuje treści i nie przekazuje jej zwykłym automatycznym
poleceniom. To konwencja współpracy aplikacji, a nie gwarancja systemowa ani
dowód, że każda nieoznaczona treść jest zwykłym tekstem.

### Obecna odpowiedź CPB na pytania kontrolne

| Pytanie | Ustalenie |
| --- | --- |
| Czy CPB odczytuje listę formatów? | **Tak.** Robi to rozszerzenie przed transferem tekstu. |
| Czy rozpoznaje format znacznika? | **Nie.** Zamknięta lista zawiera tylko dwa typy tekstowe. |
| Czy odczytuje wartość `secret`? | **Nie.** Nie wykonuje transferu tego formatu. |
| Czy detekcja bazuje wyłącznie na tekście? | **Tak** w aktualnej automatycznej ścieżce. Identyfikator aplikacji służy metadanym, nie decyzji o sekrecie. |
| Czy nazwę formatu można poznać przed tekstem? | **Tak.** Nie wolno jednak utożsamiać obecności z wartością `secret`. |
| Czy można dodać obsługę bez nowych uprawnień? | **Prawdopodobnie tak.** Ten sam obiekt `Meta.Selection` może poprosić o oferowany format. Potrzebny jest prototyp i test LIVE. |
| Czy Python może odczytać znacznik samodzielnie? | **Nie** w obecnej architekturze; nie odczytuje systemowego schowka. |

### Ograniczenie GTK 4

`x-kde-passwordManagerHint` nie jest poprawnym internetowym typem MIME, bo nie
zawiera ukośnika. Zgłoszenie KeePassXC #12696 dokumentuje, że aplikacje oparte
na wiązaniach GTK mogą nie widzieć tego formatu i proponuje równoległy,
poprawny typ. GTK 4 udostępnia `Gdk.Clipboard.get_formats()` i
`read_async()`, ale ich kontrakt jest zbudowany wokół typów MIME. Dlatego
obecność znacznika u producenta nie gwarantuje, że każda warstwa GTK lub portal
go zachowa.

Aktualna ścieżka CPB nie przechodzi przez `Gdk.Clipboard`: właścicielem odczytu
jest rozszerzenie GNOME Shell i `Meta.Selection`. GTK jest używane dopiero w
procesach interfejsu uruchamianych na żądanie, które dostają treść przez stdin.
Ograniczenie GTK 4 jest więc istotne przede wszystkim dla aplikacji źródłowej
i ewentualnych pośredników, nie dla `bridge.py`.

## Zachowanie źródeł danych

| Scenariusz | Dowody | Ocena dla CPB 1.2 |
| --- | --- | --- |
| Bitwarden Desktop, bezpośredni backend linuksowy | PR #15393 został scalony 10 lipca 2025. Kod używa `arboard::SetExtLinux::exclude_from_history()`, które dodaje znacznik KDE. | CPB nadal ignoruje znacznik i polega na tekście. LIVE na GNOME 50 niewykonany. |
| Bitwarden Desktop, portal GNOME/Wayland | Aktualny `portal_backend.rs` jawnie ignoruje flagę hasła i oferuje tylko `text/plain;charset=utf-8`; komentarz źródłowy mówi, że element pozostanie w historii dla tej ścieżki. | Znacznika nie ma do odczytania. Ochronę zapewnia tylko analiza treści CPB. |
| Bitwarden w Firefox | Dokumentacja WebExtensions potwierdza tekstowy zapis schowka, ale nie znaleziono dowodu, że linuksowa wartość KDE jest ustawiana przez tę ścieżkę. | Traktować jako nieoznaczone źródło do czasu konkretnego testu LIVE. |
| KeePassXC Desktop | Aktualny `Clipboard.cpp` na Unix ustawia tekst oraz `x-kde-passwordManagerHint=secret`. | CPB może potencjalnie zobaczyć nazwę przez `Meta.Selection`, ale obecnie jej nie używa. Transport na GNOME/Wayland wymaga testu LIVE. |
| `keepassxc-cli` | Zgłoszenie #12700 pokazuje, że ścieżka CLI nie używa wspólnej implementacji GUI i nie ustawia znacznika; problem pozostawał otwarty w czasie badania. | Brak znacznika; pozostaje detekcja tekstowa i polityka entropii. |
| Inne narzędzie CLI | Nie ma ogólnej gwarancji. Program musiałby jawnie zaoferować odpowiedni format i wartość. | Domyślnie traktować jako brak metadanych. |
| Zwykła aplikacja GTK 4 | Standardowe kopiowanie tekstu nie oznacza go automatycznie jako sekret. Niepoprawna nazwa formatu może nie przejść przez warstwy GTK. | Brak znacznika nie jest sygnałem bezpieczeństwa. |
| Zwykła aplikacja bez znacznika | Może skopiować hasło, token albo losowy identyfikator. | CPB używa reguł treści i pomocniczej polityki entropii; nadal możliwe są false negative i false positive. |

Wersja aplikacji, sposób instalacji, backend schowka i użycie portalu są częścią
scenariusza. Nie należy przenosić wyniku z wersji desktopowej na rozszerzenie
przeglądarkowe ani z XWayland na portal GNOME.

## Audyt zasad historii CPB

### Co działa prawidłowo

- **Detekcja poprzedza decyzję o liście RAM.** Rozszerzenie czeka na poprawną
  odpowiedź mostu i dopiero wtedy może wywołać `_rememberRecentClipboard()`.
- **Filtry ostrzeżeń nie sterują historią tekstową.** Decyzja historii używa
  pełnych detekcji. Test
  `test_disabled_warning_filter_does_not_enable_secret_history` potwierdza,
  że wyłączony filtr sekretu nie otwiera drogi do listy RAM.
- **Kategorie sekretów oraz całe ryzyko `high` i `critical` są odrzucane.**
  Zasada jest zapisana bezpośrednio w `history_policy.py`.
- **Wyłączenie zapisywania historii działa niezależnie od analizy.** Przy
  niepustej liście wymaga potwierdzenia podającego liczbę usuwanych wpisów;
  po potwierdzeniu czyści listę, zamyka jej proces, unieważnia sekwencję i
  blokuje kolejne dodania. Anulowanie zachowuje listę i ustawienie. Analiza
  i banner mogą nadal działać.
- **Pauza jest bramką odczytu.** Rozszerzenie nie rozpoczyna transferu, worker
  jest zatrzymywany, a Python ponownie odrzuca zdarzenie przed analizą i
  zapisem metadanych. Pauza nie zmienia trwałej preferencji historii.
- **Opóźniony callback nie powinien dopisać starej treści.** Sekwencje analizy,
  zdarzenia i ustawienia historii unieważniają nieaktualne wyniki.
- **Edytor nie tworzy wpisu zwykłą ścieżką obserwacji.** Zdarzenia od
  `io.github.copypastebin.Editor` są pomijane, a zatwierdzone własne zapisy
  aktualizują ulotną tożsamość schowka.
- **Błędy i automatyczna odpowiedź nie zawierają tekstu.** Wyjątki mają stałe,
  redagowane komunikaty, stderr procesów pomocniczych jest wyciszony, a JSON
  mostu zawiera wyłącznie zamknięte metadane. Testy canary sprawdzają brak
  treści w plikach stanu, `repr` i odpowiedziach.

### Dwie różne historie

1. **Sesyjna lista tekstów w rozszerzeniu:** maksymalnie 15 pozycji, 256 KiB na
   pozycję i 2 MiB łącznie; tylko wartości z `history_eligible=true`.
2. **Trwała historia techniczna w SQLite:** zapisuje HMAC, metadane ryzyka,
   rozmiar, źródło i relację duplikatu także dla rozpoznanego sekretu. Nie
   zapisuje oryginału, anonimizacji ani fragmentu. Klucz HMAC jest losowy i
   lokalny.

Decyzja „sekrety nie trafiają do historii schowka” dotyczy kopii treści w
liście RAM. Trwały HMAC jest technicznym identyfikatorem, a nie kopią do
ponownego wklejenia. To rozróżnienie powinno pozostać jawne.

### Czyszczenie i pamięć

`clearRecentClipboardState()` nadpisuje pole `text` pustym ciągiem, usuwa
wpisy z tablicy i zeruje licznik. Usuwanie starszych wpisów robi to samo dla
usuwanego obiektu. Jest to poprawne zwolnienie referencji zarządzanych przez
CPB, ale nie kryptograficzne wymazanie.

GJS i Python używają niemutowalnych łańcuchów, buforów transferu, kodowań UTF-8
i automatycznego garbage collectora. Kopie mogą pozostać do czasu zwolnienia
pamięci, a także znaleźć się w swapie, hibernacji lub zrzucie procesu. CPB nie
może obiecać bezpiecznego nadpisania wszystkich bajtów.

Program nie kontroluje historii utrzymywanej przez GNOME, rozszerzenia,
CopyQ, GPaste, przeglądarkę ani inne lokalne aplikacje. Wyczyszczenie bieżącego
schowka przez menedżer haseł nie usuwa kopii, którą inny program zapisał
wcześniej. Najważniejszym zabezpieczeniem jest zapobieganie zapisowi.

## Heurystyka wysokiej entropii

Pomocnicza polityka obejmuje samodzielne ciągi o długości 12–128 znaków,
odpowiedniej różnorodności, co najmniej trzech klasach znaków oraz entropii co
najmniej 3,5 bita na znak. Nie tworzy bannera; jedynie blokuje listę RAM.

### Naprawione poprawkami polityki historii

Dowolny znak `@` wcześniej kończył analizę heurystyczną. Syntetyczny test
potwierdził, że mocne hasło z `@`, którego nie rozpoznawały reguły treści,
otrzymywało `history_eligible=true`.

Nowa logika zwalnia z heurystyki tylko tekst, dla którego pełna lista detekcji
zawiera adres e-mail obejmujący cały tekst. Hasło z `@`, które nie jest pełnym
adresem e-mail, przechodzi ocenę klas, entropii i różnorodności.

Osobna poprawka tworzy wyłącznie na potrzeby heurystyki kandydata pozbawionego
dokładnie jednego końcowego `LF` albo `CRLF`. Oryginalny tekst nie jest
zmieniany. Hasło zakończone jednym takim znacznikiem podlega tym samym progom co
jego rdzeń, natomiast pełny adres e-mail, URL i ścieżka zachowują swoje
dotychczasowe wyjątki.

Kosztem tej zmiany jest objęcie tą samą decyzją także nierozpoznanych,
wysokoentropijnych identyfikatorów technicznych zakończonych jednym znacznikiem
linii. Dwa syntetyczne przykłady były odrzucane już bez zakończenia linii;
poprawka zachowuje tę decyzję również dla `LF` i `CRLF`.

### Pozostałe świadome ograniczenia

- początkowy lub wewnętrzny biały znak, końcowa spacja, tabulator albo samotny
  `CR` oraz dwa lub więcej końcowych znaków nowej linii wyłączają heurystykę;
- `://` wyłącza heurystykę;
- prefiksy `/`, `./` i `../` wyłączają heurystykę;
- długość poza zakresem 12–128 nie jest oceniana;
- ciąg spełniający składnię pełnego adresu e-mail pozostaje adresem e-mail,
  nawet jeśli człowiek zamierzał użyć go jako hasła.

Syntetyczna próba potwierdziła, że pozostałe białe znaki, `://` i prefiksy
ścieżek mogą również przepuścić ciąg spełniający progi entropii. Nie zmieniono
ich automatycznie, ponieważ chronią przed fałszywym odrzucaniem zwykłych
ścieżek, adresów URL i tekstów z odstępami. Każde zawężenie wymaga osobnej
macierzy przypadków dodatnich i ujemnych. Brak trafienia nadal nie jest
deklaracją bezpieczeństwa.

## Macierz regresji

| Przypadek | Oczekiwany wynik | Obecny dowód |
| --- | --- | --- |
| Zwykły tekst | Według ustawienia historii | Test polityki oraz test mostu dla bezpiecznego tekstu. |
| Tekst z potwierdzonym znacznikiem `secret` | Brak wpisu tekstowego | **Brak implementacji i testu.** Potrzebny test jednostkowy transferu oraz LIVE. |
| Rozpoznany token bez znacznika | Brak wpisu | Test polityki dla tokenu. |
| Rozpoznany klucz prywatny | Brak wpisu | Test polityki dla klucza prywatnego. |
| Rozpoznana fraza odzyskiwania | Brak wpisu | Test polityki dla poprawnej frazy syntetycznej. |
| Sekret przy wyłączonym filtrze | Brak wpisu | `test_disabled_warning_filter_does_not_enable_secret_history`. |
| Historia wyłączona | Brak nowych wpisów tekstowych | Testy ustawienia oraz źródłowe testy rozszerzenia; brak osobnego wykonywalnego testu całego callbacku GNOME. |
| Pauza | Brak odczytu, analizy i obu zapisów | Test mostu, testy ustawień i testy źródłowe rozszerzenia. |
| Losowy ciąg wysokiej entropii | Brak wpisu, bez bannera | Test polityki dla samodzielnego ciągu. |
| Mocny ciąg z `@`, niebędący e-mailem | Brak wpisu, bez bannera | Nowy test regresyjny. |
| Pełny zwykły adres e-mail | Nadal dozwolony przez heurystykę historii | Nowy test regresyjny pełnego zakresu detekcji. |
| Mocny ciąg z jednym końcowym `LF` lub `CRLF` | Brak wpisu, bez bannera | Test polityki i rzeczywistej decyzji mostu. |
| Zwykły tekst, adres e-mail, URL, ścieżka lub typowy identyfikator z jednym zakończeniem linii | Taka sama decyzja jak bez zakończenia linii | Syntetyczna macierz regresji. |
| Dwa zakończenia linii, końcowa spacja lub tabulator, początkowy biały znak albo tekst wielowierszowy | Dotychczasowy wyjątek pozostaje | Test dokumentujący; nadal potencjalne obejście dla nierozpoznanego sekretu. |
| Nieznany format lub niedostępne metadane | Kontynuacja tekstowej polityki; brak założenia bezpieczeństwa | Obecne zachowanie, lecz brak testu znacznika. |
| Czyszczenie listy RAM | Usunięcie referencji CPB bez obietnicy bezpiecznego wymazania | Testy źródłowe i przegląd `clearRecentClipboardState()`. |

## Rekomendowane dalsze działania

### Krytyczne dla bezpieczeństwa

1. **Zachować poprawkę wyjątku `@` i testy regresyjne.**
   - koszt: bardzo mały;
   - ryzyko regresji: małe, ograniczone do polityki sesyjnej historii;
   - nowe uprawnienia: brak;
   - wycofanie: pojedyncza zmiana funkcji i dwóch testów.

### Zalecane

1. **Przygotować osobne, małe zadanie obsługi potwierdzonego znacznika.**
   Najmniejszy wariant powinien w rozszerzeniu:
   - sprawdzić obecność formatu;
   - pobrać jego wartość z bardzo małym limitem;
   - zaakceptować wyłącznie dokładną wartość ASCII `secret`;
   - połączyć wynik z decyzją Pythona operatorem logicznym AND przed dodaniem
     tekstu do listy RAM;
   - przy braku lub błędzie metadanych nadal wykonać obecną analizę tekstu.

   Koszt jest mały lub średni. Nie potrzeba sieci, portalu, nowej usługi ani
   dodatkowych uprawnień. Ryzyko regresji dotyczy asynchronicznej kolejności
   transferów i zgodności GNOME Shell, dlatego wymagane są testy sekwencji,
   limitu, anulowania oraz LIVE na GNOME 50/Wayland. Sama obecność nazwy nie
   może blokować historii bez sprawdzenia wartości.

2. **Wykonać jawne testy LIVE dla konkretnych ścieżek.**
   Osobno: KeePassXC GUI, `keepassxc-cli`, Bitwarden direct/XWayland,
   Bitwarden portal GNOME, Firefox oraz prosta aplikacja GTK 4. Test powinien
   używać wyłącznie syntetycznej wartości i rejestrować jedynie listę formatów,
   wynik walidacji znacznika oraz licznik historii CPB — nigdy samą treść.

3. **Dodać wykonywalny test wyłączenia historii i spóźnionego callbacku.**
   Obecne testy źródłowe dobrze pilnują bramek, ale nie wykonują pełnego
   scenariusza: transfer rozpoczęty → historia wyłączona → odpowiedź workera.

### Możliwe do odłożenia

1. **Zmiana pozostałych wyjątków heurystyki entropii.** Najpierw potrzebny jest
   korpus syntetycznych tekstów wielowierszowych, innych białych znaków,
   identyfikatorów technicznych i haseł. Koszt mały, lecz ryzyko fałszywych
   odrzuceń średnie. Brak nowych uprawnień.
2. **Ujednolicenie lub standaryzacja znacznika.** To zależy od GTK, XDG i
   aplikacji źródłowych; CPB nie powinien tworzyć własnego quasi-standardu.
3. **Dodatkowe komunikaty UX o pominięciu historii.** Mogą ujawniać
   obserwatorowi, że skopiowano sekret, i wymagają osobnej decyzji UX.

## Wnioski z materiałów zewnętrznych

- CopyQ potwierdza, że najbezpieczniejszym zachowaniem jest niedopuszczenie
  sekretu do historii i automatycznych poleceń, a nie późniejsze kasowanie.
- KeePassXC pokazuje różnicę między GUI a CLI oraz problem niepoprawnej nazwy
  typu w bibliotekach GTK.
- Bitwarden pokazuje różnicę między bezpośrednim backendem linuksowym a portalem
  GNOME/Wayland. Ta sama aplikacja nie gwarantuje tych samych metadanych na
  każdej ścieżce.
- Mozilla opisuje, że historia i synchronizacja zmieniają schowek z mechanizmu
  chwilowego i lokalnego w trwały kanał. Oznaczanie i wykrywanie treści są
  warstwami uzupełniającymi.
- Artykuł Clipmer z 2 listopada 2026 jest wartościową mapą problemu, ale jego
  tabela jest twierdzeniem autora. Kluczowe punkty zweryfikowano tutaj w
  kodzie Bitwarden, KeePassXC, arboard i dokumentacji CopyQ.
- Opera Paste Protect dotyczy przede wszystkim hijackingu i złośliwych poleceń
  kopiowanych z WWW. Potwierdza wartość lokalnej analizy i jawnego ostrzeżenia,
  ale nie jest dowodem na obsługę historii haseł ani argumentem za monitoringiem
  użytkownika w CPB.
- Lokalność ogranicza wysyłanie danych, lecz nie chroni przed inną lokalną
  aplikacją, historią schowka, błędnym wklejeniem, swapem ani zrzutem procesu.
- Minimalizacja przechowywania jest osobnym zabezpieczeniem i pozostaje ważna
  również dla przyszłej wersji Windows.
- Korporacyjne DLP i CPB mają różne cele. Ten audyt nie uzasadnia telemetrii,
  kontroli administratora ani szerszych uprawnień.

## Źródła sprawdzone 4 listopada 2026

- [CopyQ — Security](https://github.com/hluk/CopyQ/blob/master/docs/security.rst),
  gałąź `master` w dniu badania.
- [KeePassXC — Clipboard.cpp](https://github.com/keepassxreboot/keepassxc/blob/develop/src/gui/Clipboard.cpp),
  blob `63ffaf2` z gałęzi `develop`.
- [KeePassXC #12696](https://github.com/keepassxreboot/keepassxc/issues/12696)
  — niepoprawna nazwa MIME i GTK; zgłoszenie otwarte.
- [KeePassXC #12700](https://github.com/keepassxreboot/keepassxc/issues/12700)
  — brak znacznika w CLI; zgłoszenie otwarte w czasie badania.
- [Bitwarden PR #15393](https://github.com/bitwarden/clients/pull/15393) —
  scalona obsługa `exclude_from_history` dla bezpośredniego backendu Linux.
- [Bitwarden — backend arboard](https://github.com/bitwarden/clients/blob/main/apps/desktop/desktop_native/core/src/clipboard/arboard_backend.rs),
  blob `dbbcf4b`.
- [Bitwarden — backend portalu GNOME](https://github.com/bitwarden/clients/blob/main/apps/desktop/desktop_native/core/src/clipboard/portal_backend.rs),
  blob `6158c29`.
- [arboard — backend Linux/X11](https://github.com/1Password/arboard/blob/master/src/platform/linux/x11.rs),
  bieżąca gałąź `master`.
- [GTK 4 — `Gdk.Clipboard.get_formats()`](https://docs.gtk.org/gdk4/method.Clipboard.get_formats.html)
  i [`read_async()`](https://docs.gtk.org/gdk4/method.Clipboard.read_async.html),
  dokumentacja biblioteki 4.24.1 wygenerowana przez gi-docgen 2026.1.
- [Mozilla — Preventing secrets from leaking through Clipboard](https://blog.mozilla.org/security/2021/12/15/preventing-secrets-from-leaking-through-clipboard/),
  15 grudnia 2021.
- [Clipmer — Your clipboard manager is keeping your passwords](https://clipmer.app/blog/clipboard-manager-saving-passwords-linux),
  2 listopada 2026; źródło wtórne.
- [Opera — Paste Protect](https://help.opera.com/en/latest/features/#paste-protect),
  dokumentacja aktualna w dniu badania.
- [GPaste](https://github.com/Keruspe/GPaste), bieżąca dokumentacja repozytorium
  w dniu badania.

## Granica końcowa

Ochrona użytkownika wymaga warstw: potwierdzonego znacznika, analizy treści,
niezależnej polityki historii i minimalizacji przechowywania. Żadna pojedyncza
warstwa nie dowodzi, że tekst jest bezpieczny. Obsługa znacznika jest
uzasadnionym przyszłym wzmocnieniem, ale nie powinna być wdrażana bez małego
prototypu i testów dla rzeczywistej ścieżki GNOME 50/Wayland.
