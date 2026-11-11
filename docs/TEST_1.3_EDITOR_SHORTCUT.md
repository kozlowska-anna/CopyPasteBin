# CopyPasteBin 1.3 — test LIVE skrótu edytora

Status: procedura przygotowana, niewykonana

## Granica testu

Test wykonuje się wyłącznie w osobnej maszynie wirtualnej, systemie LIVE albo
dedykowanym profilu testowym, w którym nie ma stabilnego CopyPasteBin 1.2.1.
Rozszerzenie 1.3 używa tego samego UUID co wydanie stabilne, więc instalacja w
profilu produkcyjnym zastąpiłaby jego pliki. Jeśli poniższa kontrola znajdzie
już rozszerzenie, należy przerwać test zamiast używać `--force`:

```bash
gnome-extensions info copypastebin@kozlowska-anna.github.io
```

Nie wolno odczytywać ani używać prawdziwej historii schowka. Wszystkie próby
wykonuje się na tekście syntetycznym, np. `synthetic editor shortcut test`.

## Artefakt deweloperski

Na czystym checkoutcie zatwierdzonego commita gałęzi 1.3:

```bash
CPB_BUNDLE_CHANNEL=development \
CPB_BUNDLE_DIST_DIR=/tmp/copypastebin-1.3-shortcut \
./packaging/build-offline-bundle.sh
sha256sum --check /tmp/copypastebin-1.3-shortcut/SHA256SUMS
```

Archiwum należy przenieść do odizolowanego systemu testowego i zainstalować
zgodnie z zawartym `INSTALL.md` lub `INSTALL.pl.md`. Instalator jest lokalny
dla użytkownika i nie wymaga `sudo`. Zależności systemowe przygotowuje się
wcześniej w obrazie testowym; nie są częścią tej procedury.

## Macierz środowisk

- Ubuntu 26.04, GNOME Shell 50, Wayland;
- Fedora 44, GNOME Shell 50, Wayland.

W obu środowiskach zapisać dokładne wersje GNOME Shell, GJS i GLib oraz wynik
każdego punktu jako PASS/FAIL.

## Scenariusze

1. Po pierwszym uruchomieniu otworzyć menu CopyPasteBin. Pozycja edytora nie
   może pokazywać skrótu, a `Super+Shift+E` nie może otwierać edytora.
2. Otworzyć preferencje rozszerzenia, wybrać `Super+Shift+E`, zamknąć
   preferencje i ponownie otworzyć menu. Pozycja edytora ma pokazywać dokładnie
   `Super+Shift+E`, bez restartu Shell.
3. Ustawić syntetyczny tekst w schowku i nacisnąć skrót. Ma powstać jedno okno
   istniejącego edytora, z tym samym tekstem i bez automatycznej zmiany
   schowka.
4. Przy otwartym edytorze nacisnąć i przytrzymać skrót. Istniejące okno ma
   zostać przywrócone na wierzch; nie mogą powstać kolejne procesy ani okna.
5. Anulować edycję i potwierdzić, że syntetyczny schowek nie został zmieniony.
   Powtórzyć próbę z jawnym „Zastąp schowek” i sprawdzić tylko oczekiwany wynik.
6. Włączyć pauzę CopyPasteBin i nacisnąć skrót. Edytor nie może pobrać tekstu
   ani się otworzyć; interfejs ma poprosić o wznowienie ochrony.
7. Zablokować ekran, nacisnąć skrót, odblokować ekran. Edytor nie może pojawić
   się podczas blokady ani po odblokowaniu wskutek wcześniejszego naciśnięcia.
8. Wyłączyć skrót w preferencjach. Etykieta ma zniknąć natychmiast, a
   `Super+Shift+E` przestać działać. Ponowne włączenie ma zarejestrować jedną
   akcję.
9. Wyłączyć całe rozszerzenie. Skrót musi zostać usunięty. Po ponownym
   włączeniu rozszerzenia ma wrócić tylko wtedy, gdy nadal jest jawnie
   skonfigurowany.
10. W odizolowanym profilu przypisać `Super+Shift+E` innej nieszkodliwej akcji
    systemowej, następnie włączyć skrót CopyPasteBin. CopyPasteBin nie może
    przejąć kombinacji; menu ma pokazać „skrót niedostępny”. Po usunięciu
    konfliktu i ponownym wybraniu ustawienia skrót ma działać.
11. Sprawdzić, że zwykłe `Ctrl+C`, `Ctrl+V`, wpisywanie tekstu i pozostałe
    funkcje menu zachowują dotychczasowe działanie.

## Zakończenie

Odinstalować wyłącznie deweloperską instalację z odizolowanego profilu. Nie
kopiować jego ustawień ani historii do profilu stabilnego. Raport powinien
zawierać commit, sumę SHA-256 artefaktu, środowisko, wyniki scenariuszy i
ewentualne komunikaty błędów bez treści schowka.
