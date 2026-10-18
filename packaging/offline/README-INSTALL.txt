COPYPASTEBIN 1.0.0 - INSTALACJA OFFLINE

Autorka: Anna Kozłowska
Rozwój wspierany przy użyciu ChatGPT i Codex od OpenAI.
CopyPasteBin jest niezależnym projektem i nie jest oficjalnym produktem ani
projektem sponsorowanym przez OpenAI.
Copyright © 2026 Anna Kozłowska. Licencja: GPL-3.0-or-later.
Pełne warunki oraz informacje o danych stron trzecich zawierają pliki LICENSE
i NOTICE dołączone do pakietu.

Pakiet instaluje CopyPasteBin tylko dla bieżącej użytkowniczki. Nie wymaga
sudo, nie łączy się z siecią i nie przenosi ustawień, historii ani zawartości
schowka z pierwszego komputera.

WYMAGANIA

- Linux z GNOME Shell 50 i sesją Wayland
- Python 3.11 lub nowszy z modułem venv
- /usr/bin/gnome-extensions i /usr/bin/gjs
- GTK 4 oraz biblioteki GObject Introspection dla GTK i GioUnix
- sha256sum

INSTALACJA

1. Rozpakuj archiwum.
2. Otwórz terminal w rozpakowanym folderze.
3. Sprawdź komputer bez wprowadzania zmian:

   ./install.sh --check-only

4. Jeżeli kontrola zakończy się wynikiem OK, zainstaluj:

   ./install.sh

5. Wyloguj się i zaloguj ponownie do sesji GNOME Wayland.
6. CopyPasteBin powinien uruchomić się automatycznie.

Jawne „Bezpieczne wklejenie” używa skrótu Super+Shift+V. Sprawdza schowek i
może przygotować propozycję redakcji, ale nie wkleja automatycznie i nie
przechwytuje zwykłego Ctrl+V.

Instalator zapisuje program w ~/.local/share. Nie zmienia prywatnych plików
w ~/.config/copypastebin ani ~/.local/state/copypastebin.

ROZWIĄZYWANIE PROBLEMÓW

Poniższy krok nie jest częścią zwykłej instalacji. Użyj go tylko wtedy, gdy
CopyPasteBin nie uruchomi się automatycznie po ponownym zalogowaniu. Zanim
uruchomisz program z menu, w rozpakowanym folderze wykonaj:

   ./diagnose-first-activation.sh

Skopiuj cały wynik. Raport nie zawiera treści schowka, historii, reguł,
wykluczeń, ścieżki katalogu domowego ani listy innych rozszerzeń. Po zapisaniu
raportu możesz uruchomić CopyPasteBin z menu aplikacji.

AKTUALIZACJA Z WERSJI ROBOCZEJ

Ten pakiet zastępuje roboczy UUID copypastebin@local publicznym UUID
copypastebin@kozlowska-anna.github.io. Stary kod rozszerzenia jest usuwany
dopiero po udanej instalacji nowej wersji. Błąd przywraca wcześniejszy katalog.
Prywatne ustawienia i historia pozostają w dotychczasowych katalogach.

ODINSTALOWANIE

W tym samym rozpakowanym folderze uruchom:

   ./uninstall.sh

Odinstalowanie zachowuje ustawienia i historię. Można je później usunąć
ręcznie, jeśli nie są już potrzebne.

WAŻNE OGRANICZENIE

Brak ostrzeżenia oznacza tylko, że CopyPasteBin nie wykrył znanego wzorca.
Nie jest to gwarancja bezpieczeństwa tekstu.
