# Testy wydania CopyPasteBin 1.2.1

**Polski** | [English](RELEASE_TESTS_1.2.1.en.md)

Ten dokument zapisuje zakres i wyniki testów kandydata 1.2.1. Nie rozszerza
deklarowanej kompatybilności i nie zastępuje audytu kodu.

## Tożsamość kandydata

- deklarowany commit: `f56cf8af56a00902fcc81f2338967851c7213661`;
- archiwum Fedora Live: `CopyPasteBin-linux-1.2.1-test2.tar.gz`;
- SHA-256 archiwum:
  `ecb60fd3db21170ead48689a9ac3bef480713185cc925bc38dd0105558ab5abc`;
- wersja aplikacji: `1.2.1`;
- wersja rozszerzenia GNOME: `8`.

## Fedora Live — PASS

Test wykonano 8 listopada 2026 na Fedora 44 Workstation Live, GNOME 50.0,
Wayland i Pythonie 3.14.3. Użyto instalacji lokalnej z archiwum tar.gz, bez
`sudo`. Rozszerzenie było aktywne.

Potwierdzono:

- zwykły tekst trafia do pamięciowej historii;
- poprawny adres e-mail zachowuje oczekiwane ostrzeżenie i może trafić do
  historii;
- podejrzany ciąg zawierający `@` nie omija heurystyki historii;
- dokładnie jeden końcowy `LF` ani `CRLF` nie omija heurystyki historii;
- wyłączenie niepustej historii pokazuje ostrzeżenie z prawidłową liczbą
  wpisów;
- `Anuluj` jest bezpiecznym wyborem domyślnym, a Enter zachowuje historię;
- potwierdzenie wyłącza zapisywanie i usuwa wpisy;
- wyłączenie pustej historii nie pokazuje zbędnego ostrzeżenia;
- instalacja, automatyczny start po zalogowaniu, pauza, wznowienie, edytor
  tekstu i responsywność przeszły próby dymne.

Próby `LF` i `CRLF` powtórzono po zauważeniu, że kopiowanie całego
polecenia `printf` samo tworzy dodatkowe zdarzenie schowka. Po wyczyszczeniu
historii i kontrolowanym powtórzeniu oba przypadki przeszły.

## Testowe PPA — PASS w wykonanym zakresie

Na fizycznym systemie Ubuntu Resolute wykonano aktualizację z
`1.2.1-1~test1` do `1.2.1-1~test2` bez usuwania pakietów. APT pobrał i
skonfigurował dokładnie zgodne wersje:

- `copypastebin`;
- `copypastebin-backend`;
- `gnome-shell-extension-copypastebin`.

Po ponownym zalogowaniu systemowe rozszerzenie z
`/usr/share/gnome-shell/extensions/copypastebin@kozlowska-anna.github.io`
miało wersję `8`, było włączone i miało stan `ACTIVE`. Potwierdzono
utworzenie syntetycznego wpisu historii oraz pełny przepływ ostrzeżenia:
anulowanie przez Enter, zachowanie wpisu, jawne wyłączenie z usunięciem
oraz brak ostrzeżenia przy pustej historii.

## Stabilne PPA — PASS

Na fizycznym systemie Ubuntu Resolute wykonano kontrolowane przejście z
`1.2.1-1~test2` na stabilne PPA. Przed instalacją APT wskazywał dla wszystkich
trzech pakietów tego samego kandydata `1.2.1-1`. Zainstalowano jedną operacją
dokładnie przypięte wersje:

- `copypastebin 1.2.1-1`;
- `copypastebin-backend 1.2.1-1`;
- `gnome-shell-extension-copypastebin 1.2.1-1`.

Potwierdzono brak lokalnego backendu i lokalnego rozszerzenia z instalacji
tar.gz. Aktywne rozszerzenie pochodziło wyłącznie ze ścieżki systemowej
`/usr/share/gnome-shell/extensions/copypastebin@kozlowska-anna.github.io`,
miało wersję `8` i stan `ACTIVE`.

Końcowy smoke test po przelogowaniu otrzymał PASS: zwykły tekst trafił do
pamięciowej historii, ostrzeżenie przed wyłączeniem niepustej historii podało
prawidłową liczbę wpisów, Enter wybrał bezpieczne anulowanie i zachował wpisy,
jawne potwierdzenie wyłączyło zapisywanie i wyczyściło listę, a okno
„O programie” pokazało wersję `1.2.1`.

## Finalne archiwum GitHub — PASS

Finalne `CopyPasteBin-linux-1.2.1.tar.gz` zbudowano z commita dokumentacyjnego
`eb963180f1912bf21704c54444137db4cfcc994b`. Dwie niezależne budowy były
bajtowo identyczne. SHA-256 archiwum:

`75ea7300d688402737e27ad07bc679ae6a952679cd6cffe10257a07f99d23a6b`

Porównanie rozpakowanych drzew z kandydatem `test2` wykazało różnice wyłącznie
w `SECURITY.md` i `SECURITY.pl.md`. Payload aplikacji, wheel, rozszerzenie,
instalator oraz pozostałe pliki były identyczne. Wszystkie wewnętrzne sumy
`SHA256SUMS` przeszły, a `./install.sh --check-only` zakończył się wynikiem
`Kontrola zgodności: OK` bez wprowadzania zmian.

## Granice dowodów

- test Fedora Live nie obejmował DEB ani PPA;
- test PPA obejmował aktualizację i zmienioną funkcję, a nie wszystkie
  kategorie detekcji;
- test stabilnego PPA był końcowym testem instalacji i zmienionej funkcji, a
  nie ponownym pełnym testem wszystkich możliwości aplikacji;
- nie wykonywano ponownego pełnego testu anonimizacji obrazów ani benchmarków;
- zgodność SHA-256 potwierdza tożsamość pliku, ale sama nie dowodzi
  pochodzenia kodu z deklarowanego commita.
- finalnego archiwum po zmianach wyłącznie dokumentacyjnych nie instalowano
  ponownie w sesji LIVE; jego payload aplikacji jest bajtowo zgodny z
  kandydatem `test2`, który otrzymał Fedora Live PASS.
