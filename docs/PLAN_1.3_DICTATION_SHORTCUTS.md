# CopyPasteBin 1.3 — plan skrótów i lokalnego dyktowania

Status: etap A, audyt i projekt techniczny
Data: 2026-11-11
Baza: publiczny `main`, commit `d23d4804ba0d264ada9f212dfb4923a8896ff02c`
(`Release CopyPasteBin 1.2.1`)

Ten dokument nie zatwierdza zależności audio, nie pobiera modeli i nie zmienia
zachowania wydania 1.2.1. Strona internetowa i SEO pozostają poza zakresem
bieżącego etapu.

## 1. Stan wyjściowy

- Interfejs pulpitu działa w rozszerzeniu GNOME Shell 50, a edytor tekstu jest
  osobnym procesem GJS/GTK 4 uruchamianym na żądanie.
- Rozszerzenie pobiera początkowy tekst schowka i przekazuje go do edytora przez
  `stdin`. Edytor zwraca przez `stdout` wyłącznie końcową, świadomie zapisaną
  treść albo zamknięty znacznik wyczyszczenia.
- Otwarte okno edytora jest śledzone przez rozszerzenie. Ponowne otwarcie wysyła
  do procesu sygnał prezentacji, a `disable()` kończy proces.
- Kod 1.2.1 nie ma schematu GSettings ani keybindingu. Test
  `test_safe_paste_and_keyboard_hooks_are_absent` wymusza brak dedykowanego
  mechanizmu skrótu usuniętego w 1.2; sam jawny przepływ sprawdzania w
  istniejącym edytorze pozostał dostępny z menu.
- Dokumenty `docs/architecture.md`, `docs/gnome-event-backend.md`, `SECURITY.md`
  i `docs/security.pl.md` nadal opisują usunięty `Super+Shift+V`. Jest to
  rozbieżność dokumentacji z kodem, którą trzeba poprawić przed opisaniem
  nowych skrótów jako funkcji 1.3.
- Bazowy zestaw testów na czystej gałęzi zakończył się wynikiem `391/391`.
  Nie wykonano testu LIVE skrótów ani audio.

## 2. Skróty

### 2.1. Otwieranie edytora

Docelowa akcja `Super+Shift+E` powinna wywoływać istniejącą `_openEditor()`.
Rejestracja ma nastąpić dopiero po udanym probe zgodności backendu i musi być
symetrycznie usuwana w `disable()`. Callback nie może odczytywać schowka przy
blokadzie sesji, ekranie logowania ani aktywnej pauzie; obecna `_openEditor()`
już zawiera te bramki.

Ważne ograniczenie dystrybucyjne: wytyczne przeglądu GNOME Extensions zabraniają
dostarczania domyślnego skrótu współdziałającego ze schowkiem. Dlatego wspólny
artefakt rozszerzenia powinien mieć pustą wartość domyślną, a ustawienie
`Super+Shift+E` musi być jawną akcją użytkownika w preferencjach. Nie należy
przywracać dawnego keybindingu `Super+Shift+V` ani globalnego hooka klawiatury.

Minimalny projekt:

1. jeden klucz GSettings typu `as`, domyślnie `[]`;
2. preferencja „Otwórz edytor” z proponowaną wartością `Super+Shift+E`;
3. dokładnie jeden `Main.wm.addKeybinding` z
   `Meta.KeyBindingFlags.IGNORE_AUTOREPEAT` i `Shell.ActionMode.NORMAL`;
4. `removeKeybinding` w każdym cyklu `disable()`;
5. czytelny stan konfliktu lub nieudanej rejestracji, bez przejmowania
   systemowego skrótu;
6. skrót pokazywany obok pozycji menu tylko wtedy, gdy jest skonfigurowany.

Na lokalnych domyślnych schematach GNOME Shell 50.1 nie znaleziono konfliktu
`Super+Shift+E`. Nie odczytywano prywatnych skrótów użytkownika, więc konflikt
z własną konfiguracją lub innym rozszerzeniem pozostaje do testu LIVE.

### 2.2. Włączanie i zatrzymywanie dyktowania

`Super+Shift+R` powinien być skrótem okna GTK, a nie drugim keybindingiem
GNOME Shell. GTK 4 udostępnia akcje aplikacji oraz `Gtk.ShortcutController`;
skrót działa wtedy tylko w aktywnym edytorze i nie wymaga globalnego
monitorowania klawiatury.

Ta sama akcja ma obsługiwać przycisk mikrofonu i skrót. Stany powinny być
zamknięte i jawne: `unavailable`, `idle`, `starting`, `recording`, `stopping`,
`error`. Aktywny stan używa niebieskiego mikrofonu. Przycisk i opis skrótu są
nieaktywne, jeśli nie ma zgodnego silnika lub modelu.

Domyślny skrót GNOME do nagrywania ekranu to `Ctrl+Shift+Alt+R`, więc nie
koliduje z proponowanym skrótem okna. Nadal trzeba sprawdzić zachowanie na
Ubuntu 26.04 i Fedorze 44 oraz przy własnych skrótach aplikacji.

## 3. Granica procesu dyktowania

Silnik rozpoznawania i przechwytywanie audio nie powinny działać w procesie
GNOME Shell. Właścicielem sesji dyktowania ma być proces edytora:

```text
przycisk / skrót okna GTK
  -> kontroler sesji w editor.js
  -> osobny, nieuprzywilejowany worker audio/STT
  -> ograniczone ramki wyników częściowych i końcowych przez pipe
  -> aktualizacja widoku GTK w głównej pętli
```

Worker powstaje dopiero po świadomym uruchomieniu i kończy się przy ponownym
użyciu skrótu, zamknięciu okna, błędzie urządzenia, blokadzie sesji lub
zakończeniu procesu. Nie może mieć usługi systemd, stałego demona ani sieci.
Audio i transkrypcja nie trafiają do argv, env, plików tymczasowych ani logów.

Pierwsza integracja powinna pokazywać wynik tymczasowy w wydzielonym,
niebiesko oznaczonym podglądzie w obrębie edytora. Dopiero wynik końcowy jest
dodawany do `Gtk.TextBuffer` jako jedna odwracalna akcja w miejscu znacznika
utworzonego przy starcie dyktowania. Dzięki temu korekta częściowa nie
nadpisuje ręcznych zmian użytkownika i nie dubluje zatwierdzonych fragmentów.
Po ustabilizowaniu protokołu można rozważyć tymczasowy zakres bezpośrednio w
buforze, ale wymaga to osobnych testów kolizji z edycją.

Tekst rozpoznany nie może samodzielnie zastępować schowka. Nadal obowiązuje
istniejący przycisk świadomego zapisu edytora.

## 4. Eksperyment porównawczy

Eksperyment ma być niezależnym harness-em, poza ścieżką produkcyjną i bez
zmiany zależności CPB. Pierwszy zakres:

| Kandydat | Model początkowy | Rozmiar / pamięć z dokumentacji | Charakter wyników |
| --- | --- | --- | --- |
| Vosk | `vosk-model-small-pl-0.22` | 50 MB; małe modele zwykle ok. 300 MB RAM | natywne wyniki częściowe i końcowe |
| whisper.cpp | multilingual `tiny` | 75 MiB; ok. 273 MB RAM | ciągłe przeliczanie okna; przykład stream jest opisany jako naiwny |
| whisper.cpp | multilingual `base` | 142 MiB; ok. 388 MB RAM | jak wyżej; nie zakładać przewagi bez pomiaru |
| whisper.cpp | multilingual `small` | 466 MiB; ok. 852 MB RAM | punkt odniesienia jakości kosztem zasobów |

Silnik whisper.cpp i modele Whisper są na licencji MIT. Vosk API oraz wskazany
polski model są na Apache-2.0. Licencję trzeba wiązać z konkretną pozycją
manifestu modelu, a nie z nazwą całego silnika.

Każdy kandydat przechodzi ten sam test na tym samym komputerze:

- 10–15 syntetycznych polskich zdań, w tym liczby, interpunkcja, nazwy własne,
  znaki diakrytyczne i krótkie polecenia;
- trzy przebiegi na silnik/model;
- czas do pierwszego wyniku, czas stabilizacji końcowej, WER/CER, poprawność
  interpunkcji, zużycie CPU, szczyt RSS i rozmiar modelu;
- osobna obserwacja poprawek wyniku tymczasowego oraz duplikowania fragmentów;
- tryb offline po przygotowaniu modelu.

Domyślny scenariusz nie zapisuje dźwięku. Użytkownik odczytuje jawnie pokazane
zdania testowe, a harness zapisuje wyłącznie metryki i transkrypcję tych
syntetycznych zdań. Opcjonalny powtarzalny plik WAV w `/tmp` wymaga osobnej,
świadomej zgody i nie może zawierać prywatnej wypowiedzi.

Kryterium przejścia do integracji nie jest „najwyższa jakość za wszelką cenę”.
Wybrany wariant musi na sprzęcie docelowym utrzymywać interfejs responsywny,
dawać użyteczny pierwszy tekst i mieścić się w zaakceptowanym budżecie RAM.
Jeżeli Vosk wygra opóźnieniem, a whisper.cpp jakością, można rozważyć dwa
profile dopiero po udowodnieniu, że koszt utrzymania jest uzasadniony.

## 5. Modele i sieć

Brak modelu pozostawia wszystkie dotychczasowe funkcje CPB aktywne. Modeli nie
wolno dołączać do instalatora ani pobierać automatycznie.

Docelowy manifest powinien być wersjonowaną allowlistą zawierającą dla każdej
pozycji: silnik, język, nazwę, wersję, rozmiar, HTTPS URL, SHA-256, licencję i
źródło licencji. Pobranie jest możliwe tylko po kliknięciu użytkownika. Plik
trafia najpierw do prywatnego pliku częściowego, przechodzi kontrolę rozmiaru i
SHA-256, a następnie atomowe przeniesienie do
`${XDG_DATA_HOME:-~/.local/share}/copypastebin/models`.

Usuwanie dotyczy wyłącznie wybranego, zwykłego pliku lub katalogu modelu z
allowlisty, bez podążania za symlinkami. Nie wymaga `sudo`, APT ani instalacji
globalnej. Pobieranie jest jedyną planowaną funkcją sieciową i nie może działać
w tle.

## 6. Ryzyka i zabezpieczenia

| Ryzyko | Zabezpieczenie |
| --- | --- |
| mikrofon pozostaje aktywny | właścicielem jest edytor; stop przy zamknięciu, blokadzie, błędzie i ponownym skrócie; widoczny niebieski stan |
| blokada GTK przez inferencję | osobny worker i asynchroniczne, ograniczone ramki |
| nadpisanie ręcznej korekty | oddzielny podgląd częściowy; tylko wynik końcowy trafia do bufora jako jedna akcja |
| duplikowanie tekstu | identyfikator sesji i rosnący numer segmentu; częściowy wynik zastępuje tylko poprzedni częściowy |
| wyciek do logów lub crash reportu | brak treści i audio w logach, argv, env i nazwach plików; zamknięte komunikaty błędów |
| niejawny dostęp do sieci | worker inferencji bez sieci; osobny, jawny downloader modeli |
| złośliwy lub uszkodzony model | allowlista, limit rozmiaru, SHA-256 przed użyciem, zwykłe pliki bez symlinków |
| konflikt skrótu globalnego | pusty domyślny keybinding, jawna konfiguracja, brak przejmowania cudzych ustawień |
| regresja stabilności GNOME Shell | w Shell pozostaje tylko rejestracja jednej akcji; audio i STT poza procesem Shell |
| niejasna licencja modelu | licencja i źródło przypisane do każdego wpisu manifestu |
| różnice Ubuntu/Fedora | test pakietów, urządzeń PipeWire i cyklu blokady na obu systemach przed wydaniem testowym |

Nowy dostęp wymagany dopiero w dalszym etapie to wejście mikrofonowe podczas
aktywnej sesji dyktowania. Korzyścią jest lokalne wprowadzanie tekstu; ryzykiem
jest przechwycenie mowy dłużej niż oczekiwano. Ograniczenie polega na braku
demona, jawnej kontrolce, natychmiastowym stopie w granicach cyklu życia oraz
braku zapisu. Sieć jest potrzebna wyłącznie opcjonalnemu downloaderowi modeli,
nie rozpoznawaniu.

## 7. Kolejność małych zmian

1. Skorygować dokumenty 1.2.1, które nadal opisują usunięty keybinding
   `Super+Shift+V` jako aktywny.
2. Dodać konfigurowalny, domyślnie pusty skrót otwierania edytora wraz z
   preferencją proponującą `Super+Shift+E`, pełnym cleanupem i testami pakietów.
3. Dodać neutralną akcję okna `dictation.toggle` oraz prezentację
   `Super+Shift+R`, początkowo nieaktywną bez backendu dyktowania.
4. Zbudować niezależny harness Vosk/whisper.cpp i wykonać benchmark sprzętowy.
5. Dopiero po wyborze silnika zatwierdzić zależności, protokół workera i
   integrację mikrofonu.

Pierwszym małym zadaniem implementacyjnym jest punkt 2. Nie dodaje dostępu do
mikrofonu, sieci ani nowej zależności wykonawczej, a przywraca skrót w formie
zgodnej z aktualnym modelem dystrybucji i zasadą świadomej zgody.

## Źródła zewnętrzne sprawdzone w etapie A

- GNOME Shell Extensions Review Guidelines:
  <https://gjs.guide/extensions/review-guidelines/review-guidelines.html>
- GNOME GSettings i preferencje rozszerzeń:
  <https://gjs.guide/extensions/development/preferences.html>
- GTK 4 — obsługa wejścia i skrótów:
  <https://gnome.pages.gitlab.gnome.org/gtk/gtk4/input-handling.html>
- whisper.cpp README i przykład stream:
  <https://github.com/ggml-org/whisper.cpp/blob/master/README.md>
  oraz <https://github.com/ggml-org/whisper.cpp/blob/master/examples/stream/README.md>
- Vosk — lista modeli i przykład mikrofonu:
  <https://alphacephei.com/vosk/models>
  oraz <https://github.com/alphacep/vosk-api/blob/master/python/example/test_microphone.py>
- Licencje:
  <https://github.com/ggml-org/whisper.cpp/blob/master/LICENSE>,
  <https://github.com/openai/whisper/blob/main/LICENSE> i
  <https://github.com/alphacep/vosk-api/blob/master/COPYING>.
