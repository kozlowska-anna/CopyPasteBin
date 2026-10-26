# Instalacja offline

**Polski** | [English](INSTALL.md) | [Wprowadzenie](README.pl.md)

Wymagania: Linux, GNOME Shell 50, Wayland, Python 3.11+ z venv,
/usr/bin/gnome-extensions, /usr/bin/gjs, GTK 4, GioUnix i sha256sum.
KDE Plasma, Cinnamon i Xfce nie są obsługiwane.

## Instalacja

Zweryfikuj pobrane archiwum dołączonym plikiem .sha256 przed rozpakowaniem
(`sha256sum --check NAZWA_ARCHIWUM.tar.gz.sha256`). Kontynuuj wyłącznie po OK.
Rozpakuj archiwum i otwórz terminal w rozpakowanym folderze. Uruchom:

```sh
./install.sh --check-only
./install.sh
```

Pierwsze polecenie tylko sprawdza zgodność; drugie uruchom po udanej kontroli.
Wyloguj się i zaloguj ponownie do GNOME Wayland.
Instalator jest lokalny dla użytkownika, offline i bez sudo. Zapisuje kod pod
~/.local/share; nie zawiera prywatnych danych z komputera budującego paczkę.

## Aktualizacja

Zweryfikuj i rozpakuj nową paczkę do nowego folderu. Uruchom jej ./install.sh
bez wcześniejszej deinstalacji. Ustawienia w ~/.config/copypastebin i stan
w ~/.local/state/copypastebin pozostają zachowane. Migracja roboczego UUID
copypastebin@local do copypastebin@kozlowska-anna.github.io usuwa stary kod
dopiero po udanej instalacji; błąd przywraca wcześniejszy katalog.

## Odinstalowanie

W folderze bieżącej paczki uruchom:

```sh
./uninstall.sh
```

Używaj bieżącego skryptu, nie starej wersji. Usuwany jest kod, a konfiguracja
i historia pozostają w prywatnych katalogach wymienionych wyżej.

## Diagnostyka

Tylko jeśli po ponownym zalogowaniu program nie wystartuje, przed ręcznym
uruchomieniem z menu wykonaj:

```sh
./diagnose-first-activation.sh
```

Raport niczego nie zmienia i nie zawiera schowka, historii, reguł, wykluczeń,
ścieżki katalogu domowego ani listy innych rozszerzeń. Przejrzyj go przed
samodzielnym przekazaniem do zgłoszenia. Nic nie jest wysyłane automatycznie.

## Używanie i bezpieczeństwo

Super+Shift+V uruchamia Bezpieczne wklejenie na żądanie, nie wkleja automatycznie
ani nie przechwytuje Ctrl+V. [Ograniczenia ochrony](SECURITY.pl.md).
