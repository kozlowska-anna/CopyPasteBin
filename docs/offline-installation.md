# Instalacja offline

Pakiet `CopyPasteBin-offline-linux-1.0.0.tar.gz` służy do kontrolowanej,
lokalnej instalacji CopyPasteBin 1.0.0. Obsługuje wyłącznie potwierdzony zakres
produktu: GNOME Shell 50, Wayland i Python 3.11 lub nowszy.

## Zawartość pakietu

- wheel lokalnego rdzenia Python bez zależności sieciowych;
- komplet plików rozszerzenia `copypastebin@kozlowska-anna.github.io`;
- skompilowany lokalnie schemat GSettings dla pojedynczego skrótu
  `Super+Shift+V`;
- launcher, skalowalną ikonę aplikacji i ukryte mapowania tej ikony do pięciu
  okien GTK; małe ikony stanu panelu pozostają osobnymi zasobami rozszerzenia;
- instalator z trybem kontroli bez zmian;
- konserwatywny deinstalator zachowujący ustawienia i historię;
- sumy SHA-256 wszystkich elementów payloadu.

Pakiet nie zawiera konfiguracji, historii, bazy metadanych, klucza HMAC,
treści schowka ani innych danych z komputera, na którym został zbudowany.

## Granice instalatora

Instalator nie używa `sudo`, menedżera pakietów ani sieci. Zapisuje wyłącznie
do stałych katalogów bieżącego użytkownika pod `~/.local/share`. Przed zapisem
sprawdza integralność pakietu, wersję Python, GNOME Shell, dostępność `venv`,
`gjs`, GTK 4 i wymaganych bibliotek GObject. Dowiązania symboliczne w miejscach
docelowych są odrzucane.

Aktualizacja zachowuje prywatne katalogi `~/.config/copypastebin` oraz
`~/.local/state/copypastebin`. W razie błędu tworzenia nowego środowiska lub
kopiowania rozszerzenia instalator przywraca wcześniejszą wersję programu.
Zachowany stan obejmuje również wybór języka GUI. Po instalacji można wybrać
język systemu, polski albo angielski bez pobierania dodatkowych plików.

Aktualizacja wersji roboczej przenosi kod rozszerzenia z UUID
`copypastebin@local` do publicznego UUID
`copypastebin@kozlowska-anna.github.io`. Stary UUID jest wyłączany, a jego
katalog kodu usuwany dopiero po udanej instalacji nowej wersji. Błąd
instalacji przywraca stary katalog. Konfiguracja i stan CopyPasteBin nie są
powiązane z UUID i pozostają w dotychczasowych prywatnych katalogach.

## Procedura użytkownika

Po rozpakowaniu pakietu należy najpierw wykonać:

```text
./install.sh --check-only
```

Polecenie niczego nie instaluje. Po wyniku `Kontrola zgodności: OK` właściwa
instalacja wymaga:

```text
./install.sh
```

GNOME Shell na Waylandzie ładuje nowe lokalne rozszerzenie po ponownym
zalogowaniu. Instalator zapisuje publiczny UUID na liście włączonych rozszerzeń,
zachowując wszystkie pozostałe wpisy i usuwając wyłącznie dawny roboczy UUID.
Nie wymaga to usługi, opóźnienia ani dodatkowego dostępu do schowka. Po
ponownym zalogowaniu CopyPasteBin powinien uruchomić się automatycznie.

Do ewentualnej diagnostyki, przed uruchomieniem pozycji z menu aplikacji, można
w rozpakowanym folderze wykonać:

```text
./diagnose-first-activation.sh
```

Raport pokazuje wyłącznie techniczny stan sesji, rozpoznania i włączenia UUID
oraz właściwych ustawień GNOME. Nie wypisuje treści schowka, prywatnych danych
CopyPasteBin, ścieżki katalogu domowego ani nazw innych rozszerzeń. Test niczego
nie zmienia. Jeżeli automatyczny start nie nastąpił, po zapisaniu całego wyniku
można uruchomić CopyPasteBin z menu aplikacji.

Deinstalacja używa `./uninstall.sh` z bieżącego pakietu. Nie należy uruchamiać
deinstalatora ze starego rozpakowanego katalogu, ponieważ starsza wersja może
nie znać publicznego UUID. Bieżący skrypt usuwa kod i launcher dla publicznego
UUID oraz pozostałość starego UUID, ale świadomie pozostawia lokalne ustawienia
i historię.
