# Testy wydania CopyPasteBin 1.2.2

**Polski** | [English](RELEASE_TESTS_1.2.2.en.md)

Ten dokument zapisuje przygotowanie i testy kandydata 1.2.2 po usunięciu
dawnego watchera pollingowego. Nie rozszerza deklarowanej kompatybilności.

## Tożsamość kandydata

- commit zweryfikowanego kodu i konfiguracji wydania:
  `415e2264dbeb23faf44d4a2b1cf68662675221bf`;
- wersja aplikacji: `1.2.2`;
- wersja pakietów Debiana: `1.2.2-1`;
- wersja przetestowana z PPA: `1.2.2-1~test1`, z commita uploadowego
  `603e3ae2452f5c4f9318062f93cf7ebf8f11df7c`;
- stabilne źródło PPA zbudowano ze scalonego commita `main`
  `7653fa317b72336695ce03f39c35fa74f28f50fb`;
- wersja rozszerzenia GNOME: `8` (bez zmian kodu rozszerzenia wymagających
  nowej wersji metadanych);
- gałąź lokalna: `codex/cpb-1.2.2-release`.

## Testy automatyczne — PASS

22 listopada 2026 na Linuksie wykonano:

- 291 testów produktu, integracji, bezpieczeństwa, instalacji i pakowania;
- 26 testów statycznej strony;
- łącznie 317 z 317 testów zakończonych wynikiem PASS;
- `git diff --check` bez błędów.

Testy pakowania obejmowały budowę paczki offline, trzy rozdzielone pakiety
DEB, migrację instalacji oraz budowę źródłowego pakietu Debiana z bieżącego
commita.

## Powtarzalność i tożsamość artefaktów — PASS

Dwa niezależne przebiegi budowy dały bajtowo identyczne pliki w obrębie
każdego rodzaju artefaktu. SHA-256 lokalnych kandydatów:

- `CopyPasteBin-linux-1.2.2.tar.gz`:
  `53a86553690aa9eb3d38c3277bd2fd40eaf688c2bdbf5a72fb47c797ab0f6715`;
- `copypastebin-backend_1.2.2-1_all.deb`:
  `b949e5cebbaeebdafe38712e88fad2e5aaa232ca76bd1481b3f3a2febf692f58`;
- `gnome-shell-extension-copypastebin_1.2.2-1_all.deb`:
  `23ac0d468e776a4e0ede33f2ca73c82b73efcb69106fa7ccbc67d7a372c674ae`;
- `copypastebin_1.2.2-1_all.deb`:
  `abe221d435663eac5fca57d4662fd80b30783a63529f1184899e909cc3051fa2`.

To są artefakty lokalne z katalogu tymczasowego, a nie opublikowane pliki
GitHub Release lub PPA.

## Izolowany test instalacji — PASS

Test przeprowadzono wyłącznie na syntetycznym katalogu domowym i stanie:

- `install.sh --check-only` potwierdził zgodność bez zmian;
- instalacja lokalna z `--no-enable` zakończyła się poprawnie;
- backend zwrócił wersję produktu `1.2.2` i protokołu `2`;
- usunięte polecenie `cpb watch start` zakończyło się zwykłym błędem
  argumentów z kodem `2`;
- uninstall usunął kod aplikacji i rozszerzenia;
- syntetyczna konfiguracja i syntetyczny stan zostały zachowane;
- nie utworzono dawnej usługi `copypastebin-watcher.service` ani launchera
  `copypastebin-start.desktop`.

Kontrola zawartości archiwum i pakietów DEB nie wykazała modułów watchera,
usługi, dawnego launchera ani plików audio lub modeli.

## Test LIVE z testowego PPA — PASS

22 listopada 2026 użytkowniczka wykonała kontrolowaną aktualizację na Ubuntu
Resolute, GNOME Shell 50.1 i Waylandzie. Testowe PPA dostarczyło dokładnie
zgodne wersje `1.2.2-1~test1` pakietów `copypastebin`,
`copypastebin-backend` oraz `gnome-shell-extension-copypastebin`. Przed
aktualizacją potwierdzono brak lokalnej instalacji tar.gz.

Po ponownym zalogowaniu potwierdzono:

- systemowe rozszerzenie ze ścieżki `/usr/share/gnome-shell/extensions` miało
  wersję `8`, było włączone i miało stan `ACTIVE`;
- backend zgłaszał wersję produktu `1.2.2` i protokołu `2`;
- dawna usługa była nieaktywna i nieznana systemd, a pliki usługi i launchera
  nie istniały;
- nie działał proces `wl-paste`, watcher ani `cpb watch`, a `cpb watch start`
  kończył się zwykłym błędem argumentów z kodem `2`;
- menu pozostawało stabilnie otwarte, bez migania, kradzieży fokusu i
  samoczynnego zamykania;
- pauza i wznowienie działały;
- zwykła syntetyczna treść trafiała do historii;
- syntetyczne przypisanie hasła wywoływało ostrzeżenie i nie trafiało do
  historii, podczas gdy wcześniejszy zwykły wpis pozostawał;
- bezpieczne anulowanie wyłączenia zapisywania zachowywało historię;
- edytor działał na syntetycznym tekście, a okno „O programie” pokazywało
  wersję `1.2.2`.

Test nie wymagał ręcznego sprzątania pozostałości legacy, ponieważ nie były
obecne.

## Stabilne PPA — PASS

22 listopada 2026 źródło i wszystkie trzy pakiety `1.2.2-1` uzyskały status
`Published` w stabilnym PPA dla Ubuntu Resolute. Dwie niezależne budowy
źródłowe były bajtowo identyczne. Lokalnie zbudowane pakiety binarne miały te
same SHA-256 co kandydat zweryfikowany przed testem LIVE.

Użytkowniczka wykonała kontrolowane przejście ze wszystkich trzech pakietów
`1.2.2-1~test1` na dokładnie zgodny zestaw `1.2.2-1`, a następnie usunęła
testowe PPA. `apt-cache policy` wskazywał stabilne PPA jako jedyne źródło
zainstalowanej i kandydującej wersji `1.2.2-1`.

Po ponownym zalogowaniu końcowy smoke test potwierdził:

- systemowe rozszerzenie w `/usr/share` miało wersję `8` i stan `ACTIVE`;
- backend zgłaszał wersję produktu `1.2.2` i protokołu `2`;
- nie działał proces `wl-paste`, watcher ani `cpb watch`;
- menu pozostawało otwarte bez migania i samoczynnego zamykania;
- pauza i wznowienie działały;
- zwykły syntetyczny tekst trafiał do historii.

## Granice dowodów

- tag `v1.2.2` wskazuje commit
  `18d10b560716af1a17fadd38bfa2532e5e4a59e3`, a publiczny GitHub Release
  zawiera archiwum tar.gz, trzy pakiety DEB i `SHA256SUMS`;
- wszystkie publiczne assety GitHub Release przeszły kontrolę `SHA256SUMS` i
  były bajtowo identyczne z lokalnym zestawem finalnego wydania;
- stabilny pakiet `1.2.2-1` opublikowano w stabilnym PPA;
- testowy pakiet `1.2.2-1~test1` pozostał wyłącznie w testowym PPA, które po
  przejściu na wersję stabilną usunięto z konfiguracji komputera testowego;
- komputer testowy został świadomie zaktualizowany ze stabilnego `1.2.1-1` do
  kandydata z testowego PPA, a następnie do stabilnego `1.2.2-1`;
- nie odczytywano prawdziwego schowka, historii ani prywatnych danych;
- wyniki interakcji z GNOME są dowodem LIVE zgłoszonym przez użytkowniczkę;
- zgodność SHA-256 potwierdza tożsamość pliku, ale sama nie dowodzi jego
  pochodzenia z deklarowanego commita.
