# Testy wydania CopyPasteBin 1.2.2

**Polski** | [English](RELEASE_TESTS_1.2.2.en.md)

Ten dokument zapisuje przygotowanie kandydata 1.2.2 po usunięciu dawnego
watchera pollingowego. Nie rozszerza deklarowanej kompatybilności i nie
zastępuje testu LIVE w fizycznej sesji GNOME.

## Tożsamość kandydata

- commit zweryfikowanego kodu i konfiguracji wydania:
  `415e2264dbeb23faf44d4a2b1cf68662675221bf`;
- wersja aplikacji: `1.2.2`;
- wersja pakietów Debiana: `1.2.2-1`;
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

## Test LIVE — OCZEKUJE

Nie wykonano jeszcze testu na fizycznej sesji GNOME Wayland ani aktualizacji
z opublikowanej wersji 1.2.1. Przed publikacją należy co najmniej potwierdzić:

- aktualizację z 1.2.1 do dokładnie zgodnego zestawu 1.2.2;
- aktywację rozszerzenia po ponownym zalogowaniu;
- działanie menu, pauzy, wznowienia, historii i edytora na syntetycznej treści;
- brak dawnego procesu pollingowego, usługi i launchera;
- ręczne sprzątanie ewentualnych pozostałości legacy zgodnie z changelogiem.

## Granice dowodów

- nie wykonano push, tagu, GitHub Release ani publikacji PPA;
- nie zmieniono stabilnej instalacji użytkowniczki;
- nie odczytywano prawdziwego schowka, historii ani prywatnych danych;
- PASS automatyczny nie jest oznaczony jako PASS LIVE;
- zgodność SHA-256 potwierdza tożsamość pliku, ale sama nie dowodzi jego
  pochodzenia z deklarowanego commita.
