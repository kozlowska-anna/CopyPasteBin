# Instalacja CopyPasteBin 1.2

CopyPasteBin 1.2 ma dwie metody instalacji z tego samego zestawu źródeł:

- trzy pakiety Debiana w dokładnie tej samej wersji z [wydania v1.2](https://github.com/kozlowska-anna/CopyPasteBin/releases/tag/v1.2): `copypastebin-backend_1.2-2_all.deb`, `gnome-shell-extension-copypastebin_1.2-2_all.deb` i `copypastebin_1.2-2_all.deb` — instalacja systemowa zarządzana przez APT;
- [archiwum `CopyPasteBin-linux-1.2.tar.gz`](https://github.com/kozlowska-anna/CopyPasteBin/releases/download/v1.2/CopyPasteBin-linux-1.2.tar.gz) — instalacja lokalna dla jednego użytkownika.

Pobierz również [`SHA256SUMS`](https://github.com/kozlowska-anna/CopyPasteBin/releases/download/v1.2/SHA256SUMS) i sprawdź wybrane pliki przed ich otwarciem. Nie instaluj obu wariantów jednocześnie.

Obsługiwany zakres to GNOME Shell 50, Wayland oraz Python 3.11 lub nowszy.
KDE Plasma, Cinnamon i Xfce nie mają potwierdzonej integracji. Projekt nie ma
Pakiety nie dodają repozytorium APT ani klucza podpisującego. Lokalnie pobrane
pliki DEB nie otrzymują automatycznych aktualizacji, chyba że użytkownik osobno
skonfiguruje opublikowane repozytorium.

## Wspólna zawartość

- wheel lokalnego rdzenia Python bez zależności sieciowych;
- komplet plików rozszerzenia `copypastebin@kozlowska-anna.github.io`;
- launcher, skalowalną ikonę aplikacji i ukryte mapowania tej ikony do sześciu
  okien GTK; małe ikony stanu panelu pozostają osobnymi zasobami rozszerzenia;
- uruchamiany wyłącznie na polecenie edytor obrazów dla lokalnych plików PNG i
  JPEG, zapisujący zanonimizowany wynik jako nowy plik PNG;
- instalator z trybem kontroli bez zmian;
- konserwatywny deinstalator zachowujący ustawienia i historię;
- sumy SHA-256 wszystkich elementów payloadu.

Pakiet nie zawiera konfiguracji, historii, bazy metadanych, klucza HMAC,
treści schowka ani innych danych z komputera, na którym został zbudowany.

## Archiwum tar.gz

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

Po rozpakowaniu pakietu uruchom terminal w jego folderze. Można na przykład
użyć opcji **Otwórz w terminalu** w menu kontekstowym menedżera plików.
Następnie sprawdź zgodność systemu:

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

Aby ręcznie zaktualizować instalację tar.gz, pobierz i sprawdź nowe wydanie,
rozpakuj je do nowego katalogu i uruchom zawarty w nim `./install.sh`. Nie
odinstalowuj najpierw istniejącej wersji. Aby otrzymywać powiadomienia o nowych
wersjach, otwórz [repozytorium CopyPasteBin na
GitHubie](https://github.com/kozlowska-anna/CopyPasteBin) i wybierz **Watch →
Custom → Releases**. Powiadomienia wymagają konta GitHub i nie aktualizują
programu automatycznie.

Deinstalacja używa `./uninstall.sh` z bieżącego pakietu. Nie należy uruchamiać
deinstalatora ze starego rozpakowanego katalogu, ponieważ starsza wersja może
nie znać publicznego UUID. Bieżący skrypt usuwa kod i launcher dla publicznego
UUID oraz pozostałość starego UUID, ale świadomie pozostawia lokalne ustawienia
i historię. Po dodaniu albo usunięciu własnej ikony instalator i deinstalator
przebudowują wyłącznie standardowy cache ikon `hicolor` bieżącego użytkownika.

## Gdy CopyPasteBin nie uruchomi się automatycznie

Ten krok diagnostyczny nie jest częścią zwykłej instalacji. Użyj go tylko
wtedy, gdy CopyPasteBin nie pojawi się po ponownym zalogowaniu. Przed ręcznym
uruchomieniem programu wykonaj w rozpakowanym folderze:

```text
./diagnose-first-activation.sh
```

Raport pokazuje wyłącznie techniczny stan sesji, rozpoznania i włączenia UUID
oraz właściwych ustawień GNOME. Nie wypisuje treści schowka, prywatnych danych
CopyPasteBin, ścieżki katalogu domowego ani nazw innych rozszerzeń. Test niczego
nie zmienia. Po zapisaniu całego wyniku można uruchomić CopyPasteBin z menu
aplikacji.

## Pakiet DEB

Przed instalacją sprawdź sumę oraz metadane pobranego pliku:

```text
sha256sum --check --ignore-missing SHA256SUMS
dpkg-deb --info copypastebin-backend_1.2-2_all.deb
dpkg-deb --info gnome-shell-extension-copypastebin_1.2-2_all.deb
dpkg-deb --info copypastebin_1.2-2_all.deb
```

Instalacja systemowa wymaga zatwierdzenia uprawnień administratora:

```text
sudo apt install \
  ./copypastebin-backend_1.2-2_all.deb \
  ./gnome-shell-extension-copypastebin_1.2-2_all.deb \
  ./copypastebin_1.2-2_all.deb
```

Pakiet nie uruchamia CopyPasteBin jako root, nie ma skryptów maintainer i nie
włącza rozszerzenia podczas instalacji. Po instalacji wyloguj się, zaloguj do
GNOME Wayland i uruchom pozycję „CopyPasteBin”. Aktualizacja używa tej
samej komendy z nowym plikiem DEB. Centrum oprogramowania Ubuntu nie
zaktualizowało istniejącego lokalnego pakietu podczas testu, dlatego
udokumentowaną metodą aktualizacji jest APT.

Odinstalowanie kodu pakietu:

```text
sudo apt remove \
  copypastebin \
  gnome-shell-extension-copypastebin \
  copypastebin-backend
```

Prywatne katalogi `~/.config/copypastebin` i
`~/.local/state/copypastebin` pozostają. Graficzny instalator Ubuntu może
opisywać lokalny, niepodpisany DEB jako pochodzący od nieznanego wydawcy albo
mający nieograniczone uprawnienia. Bez podpisanego repozytorium lub sandboxa
metadane pakietu nie mogą uczciwie usunąć tych komunikatów.

## Zmiana metody instalacji

Przy przejściu z tar.gz do DEB najpierw uruchom `./uninstall.sh` z aktualnego
archiwum, a dopiero potem zainstaluj DEB. Skrypt zachowa ustawienia i historię,
ale usunie lokalny backend, launchery oraz rozszerzenie o tym samym UUID, które
miałoby pierwszeństwo przed wersją systemową. Helper DEB odmawia aktywacji,
jeśli taki konflikt nadal istnieje; nie usuwa go automatycznie. Podczas jawnej
aktywacji helper odświeża cache ikon bieżącego użytkownika, aby stary wpis po
wcześniejszym `tar.gz` nie przesłaniał poprawnej ikony systemowej. Operacja nie
odczytuje ustawień, historii ani treści schowka i nie jest warunkiem aktywacji.

Przy przejściu z DEB do tar.gz najpierw usuń pakiet poleceniem `apt remove`, a
następnie użyj `./install.sh` z archiwum. Nie instaluj obu wariantów
jednocześnie. Ponowna instalacja tej samej wersji nie usuwa prywatnego stanu.
