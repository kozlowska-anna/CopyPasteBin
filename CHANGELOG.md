# Changelog

Wszystkie istotne zmiany CopyPasteBin są zapisywane w tym pliku.

## [1.1] - 2026-10-26

### Dodano

- uruchamiany na żądanie edytor GTK 4 do trwałego zakrywania
  prostokątnych obszarów w lokalnych plikach PNG i JPEG;
- zapis wyłącznie jako nowy plik PNG bez metadanych źródła, z możliwością
  cofnięcia ostatniego zakrycia;
- limity rozmiaru wejścia i wymiarów obrazu oraz testy na syntetycznych
  plikach PNG i JPEG;
- natywny pakiet Debian `1.1-1` obok lokalnego dla użytkownika archiwum
  tar.gz.

### Granice

- edytor obrazów nie przechwytuje ekranu, nie monitoruje obrazów w schowku,
  nie używa sieci i nie nadpisuje istniejących plików;
- wybór pliku korzysta z systemowego okna GTK, więc środowisko graficzne może
  tworzyć własne miniatury lub wpisy ostatnich plików;
- wydanie nie deklaruje kryptograficznego wymazywania obrazu z pamięci RAM.

### Pakowanie i zgodność

- DEB i tar.gz powstają z tego samego zestawu źródeł oraz zawierają ten sam
  backend, rozszerzenie GNOME, edytory, ikony i ustawienia domyślne;
- pakiet DEB nie zawiera skryptów maintainer, nie uruchamia programu i nie
  włącza rozszerzenia podczas instalacji wykonywanej przez administratora;
- wspólny resolver backendu preferuje `/usr/bin/cpb`, następnie kontrolowany
  backend instalacji użytkownika, i nie przeszukuje `PATH`;
- aktualizacja i deinstalacja zachowują `~/.config/copypastebin` oraz
  `~/.local/state/copypastebin`;
- automatyczne ostrzeżenia, poziomy ryzyka i kolorowe banery pozostają częścią
  wspólnego kodu rozszerzenia; edytor obrazu działa w osobnym procesie i nie
  korzysta ze schowka ani silnika detekcji tekstu.

## [1.0.0] - 2026-10-18

Pierwsze publiczne wydanie linuksowe.

### Dodano

- lokalne wykrywanie i anonimizację tekstu z poziomami ryzyka `low`, `medium`,
  `high` i `critical`;
- zdarzeniową integrację z GNOME Shell 50 na Waylandzie, bez pollingowego
  watchera schowka;
- skrót Bezpiecznego wklejenia `Super+Shift+V`, który analizuje tekst na
  żądanie i nie wykonuje automatycznego wklejenia;
- edytor z jawną anonimizacją zaznaczenia oraz dokładnymi wykluczeniami tylko
  dla kategorii niskiego i średniego ryzyka;
- lokalne reguły, filtry, pauzę i opcjonalne czasowe czyszczenie ostrzegającego
  schowka;
- historię metadanych bez treści oraz sesyjną listę do 15 ostatnich tekstów
  przechowywaną wyłącznie w RAM;
- polski i angielski interfejs, okno „O programie” oraz integrację wizualną z
  pulpitem;
- instalator, aktualizator, deinstalator i ograniczoną diagnostykę pierwszej
  aktywacji działające lokalnie bez `sudo` i sieci.

### Bezpieczeństwo i prywatność

- treść przechodzi między komponentami przez ograniczone `stdin`/`stdout`,
  nie przez argumenty procesu, zmienne środowiskowe ani pliki tymczasowe;
- trwała historia zapisuje metadane i HMAC, ale nie oryginalny ani
  zanonimizowany tekst;
- blokada ekranu, pauza i wyłączenie rozszerzenia odcinają odczyt i czyszczą
  sesyjną listę tekstów;
- instalator zachowuje obce rozszerzenia GNOME, odrzuca dowiązania symboliczne
  w miejscach docelowych i cofa nieudaną aktualizację;
- domyślnie wyłączone są najbardziej heurystyczne filtry `TOKEN`,
  `HOME_PATH` i `POSSIBLE_SEED_PHRASE`; filtry konkretnych sekretów pozostają
  aktywne;
- kategorie `high` i `critical` nie mogą otrzymać trwałego wykluczenia.

### Dystrybucja

- paczka offline instaluje program lokalnie dla jednego użytkownika i
  zachowuje ustawienia oraz historię podczas aktualizacji i deinstalacji;
- archiwum wydania ma znormalizowanego właściciela `0/0`, stałe znaczniki
  czasu oraz prawa `0555` dla katalogów i skryptów i `0444` dla pozostałych
  plików;
- wejście budowy wheelu jest kopiowane do tymczasowego drzewa o stałych
  prawach, dzięki czemu wynik nie zależy od lokalnego `umask` ani praw checkoutu;
- zewnętrzna suma SHA-256 pozwala sprawdzić niezmienność artefaktu.

### Kompatybilność

- potwierdzony zakres wydania to GNOME Shell 50 na Waylandzie z Pythonem 3.11
  lub nowszym;
- Linux Mint Cinnamon, KDE Plasma i Xfce nie mają w wersji 1.0 integracji
  pulpitu; instalator bezpiecznie zatrzymuje się, gdy brakuje GNOME Shell;
- obsługa innych pulpitów, OCR i wersja Windows pozostają poza zakresem tego
  wydania.

### Ograniczenia

- brak ostrzeżenia nie jest gwarancją bezpieczeństwa ani kompletności
  wykrywania;
- program nie chroni przed administratorem systemu, innym procesem tego samego
  użytkownika, menedżerem schowka, obserwacją ekranu ani przejętą aplikacją
  docelową.
