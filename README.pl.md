# <img src="website/assets/images/logo-web.svg" alt="Ikona CopyPasteBin" width="44" height="44"> CopyPasteBin

[English](README.md) | **Polski**

**[Otwórz stronę CopyPasteBin](https://kozlowska-anna.github.io/CopyPasteBin/)**

[Pobierz wersję 1.2.1](#instalacja-wersji-121) · [Dokumentacja](#dokumentacja) · [Model bezpieczeństwa](docs/security.pl.md)

## Więcej kontroli zanim wkleisz

CopyPasteBin pomaga zauważyć dane wrażliwe w skopiowanym tekście, zanim trafią
do czatu, maila, dokumentu lub terminala. Analiza działa lokalnie, a decyzja
zawsze należy do Ciebie.

### Dlaczego warto

- **Zauważasz ryzyko wcześniej.** Ostrzeżenie pojawia się, gdy tekst przypomina
  obsługiwany rodzaj danych wrażliwych.
- **Decyzja należy do Ciebie.** Program pomaga ocenić tekst, ale nie wkleja go
  i domyślnie nie zmienia schowka automatycznie.
- **Twoje dane zostają na komputerze.** Wykrywanie i anonimizacja działają bez
  wysyłania treści do chmury.
- **Łatwiej poprawiasz tekst.** Edytor pomaga usunąć albo zanonimizować
  wybrane wartości przed użyciem.

### W codziennej pracy

Kopiujesz jak zwykle. CopyPasteBin pracuje w tle i daje Ci chwilę na
sprawdzenie tekstu przed użyciem go w rozmowie, wiadomości, dokumencie lub
poleceniu.

### Ty zachowujesz kontrolę

CopyPasteBin ostrzega i proponuje poprawki, lecz zapis wymaga jawnej akcji.
Opcjonalne czyszczenie niezmienionego ostrzegającego schowka działa tylko po
świadomym włączeniu przez użytkownika.

### Uczciwie o ochronie

Brak ostrzeżenia oznacza tylko, że program nie wykrył znanego, aktywnego
wzorca. CopyPasteBin pomaga ograniczać ryzyko, ale nie gwarantuje wykrycia
wszystkich danych wrażliwych i nie blokuje wklejania.

## Najważniejsze funkcje

- **Wykrywanie danych wrażliwych:** obsługiwane wzorce obejmują między innymi
  klucze API, tokeny dostępu, klucze odzyskiwania, dane płatnicze,
  identyfikatory osobowe, adresy sieciowe, prywatne ścieżki i ciągi połączeń
  baz danych.
- **Cztery poziomy ryzyka:** niski, średni, wysoki i krytyczny.
- **Sprawdzanie i anonimizacja:** możesz obejrzeć wykryte dane i jawnie
  zastąpić schowek dopiero po sprawdzeniu wyniku.
- **Anonimizacja obrazów:** na żądanie otwórz lokalny plik PNG lub JPEG,
  zakryj wybrane obszary i zapisz nowy PNG bez modyfikowania oryginału.
- **Dokładne wykluczenia:** znane trafienie niskiego lub średniego ryzyka można
  wyciszyć bez wyłączania całej kategorii. Trafień wysokiego i krytycznego
  ryzyka nie można trwale wykluczać.
- **Lokalny model historii:** trwała historia zawiera ograniczone metadane i
  HMAC, a nie treść schowka. Do 15 ostatnich tekstów może być przechowywanych
  w pamięci bieżącej sesji; rozpoznane sekrety i tekst wysokiego ryzyka nie
  trafiają na tę listę nawet po wyłączeniu odpowiadającego im filtra ostrzeżeń.
  Zapisywanie historii można wyłączyć bez zatrzymywania analizy i edytora.
- **Konfigurowalna ochrona:** można zmieniać kategorie detekcji, dodawać własne
  reguły dosłowne, wstrzymać monitorowanie albo świadomie włączyć czyszczenie
  niezmienionego ostrzegającego schowka po 1, 5 lub 15 minutach.
- **Polski i angielski interfejs.**

CopyPasteBin nie przejmuje `Ctrl+V`, nie podsłuchuje globalnie klawiatury i
nie wkleja tekstu w imieniu użytkownika.

## CopyPasteBin na ekranie

### Ostrzeżenie o danych wrażliwych

Po wykryciu aktywnego wzorca CopyPasteBin pokazuje banner w kolorze poziomu
ryzyka. Widoczne są wyłącznie bezpieczne nazwy kategorii i liczba trafień,
nigdy treść schowka. Przycisk otwiera edytor.

<img width="594" height="140" alt="Ostrzeżenie CopyPasteBin 1.1 o wysokim ryzyku po wykryciu demonstracyjnej karty płatniczej w schowku" src="docs/screenshots/02-copypastebin-1-1-ostrzezenie-przed-wklejeniem-danych-wrazliwych-PL.png" />

### Edytor schowka

Edytor podświetla fragmenty znalezione przez lokalny detektor i przygotowuje
propozycję anonimizacji. Schowek zmienia się dopiero po kliknięciu „Zastąp
schowek”; anulowanie nie wprowadza zmian. Zrzut używa syntetycznych danych.

<img width="1076" height="606" alt="Edytor schowka CopyPasteBin 1.1 z podświetlonym demonstracyjnym adresem e-mail i hasłem przed anonimizacją" src="docs/screenshots/03-copypastebin-1-1-edytor-schowka-podswietlanie-danych-wrazliwych-PL.png" />

### Lokalna anonimizacja obrazów

Lokalny edytor pozwala ręcznie zakryć wybrane obszary i zapisać nową,
bezpieczną kopię PNG bez modyfikowania oryginalnego obrazu.

<img width="1128" height="789" alt="Edytor anonimizacji obrazów CopyPasteBin 1.1 z czterema ręcznymi zakryciami syntetycznego odbiorcy, adresu, adresu e-mail i podpisu" src="docs/screenshots/06-copypastebin-1-1-lokalny-edytor-anonimizacji-obrazow-PL.png" />

<details>
<summary><strong>Więcej zrzutów CopyPasteBin</strong></summary>

### Integracja z pulpitem GNOME

Menu pokazuje stan monitorowania i daje dostęp do sesyjnej listy ostatnich
tekstów, filtrów, reguł i wykluczeń, automatycznego czyszczenia, ustawień
języka, edytora, pauzy oraz lokalnego okna „O programie”.

<img width="411" height="613" alt="Menu CopyPasteBin 1.1 w GNOME z historią schowka, filtrami wykrywania, regułami własnymi, anonimizacją tekstu i obrazów oraz ustawieniami pauzy" src="docs/screenshots/01-copypastebin-1-1-menu-menedzera-schowka-gnome-PL.png" />

### Anonimizacja wybranego fragmentu

Kliknięcie trafienia niskiego lub średniego ryzyka wybiera jego dokładny
zakres. Można zanonimizować tylko ten fragment albo po potwierdzeniu dodać
dokładne, rozróżniające wielkość liter wykluczenie dla tej wartości i
kategorii. Trafienia wysokiego i krytycznego ryzyka można anonimizować, ale nie
można ich wykluczać.

<img width="1076" height="606" alt="Edytor CopyPasteBin 1.1 z zaznaczonym adresem e-mail, otwartymi działaniami anonimizacji i wykluczenia oraz widocznymi narzędziami poprawiania tekstu" src="docs/screenshots/04-copypastebin-1-1-selektywna-anonimizacja-narzedzia-edycji-PL.png" />

### Reguły własne i wykluczenia

Reguły własne są lokalnymi, ograniczonymi i dokładnymi literałami, które
rozróżniają wielkość liter i mają przypisany poziom ryzyka. Każdą regułę można
włączać i wyłączać. Dokładne wykluczenia działają tylko dla obsługiwanych
trafień niskiego i średniego ryzyka. Prawdziwych haseł, kluczy ani innych
sekretów nie należy zapisywać jako reguł lub wykluczeń.

<img width="1208" height="649" alt="Okno CopyPasteBin 1.1 z syntetycznymi regułami wykrywania oraz dokładnymi wykluczeniami dla przykładowego adresu e-mail i dokumentacyjnego adresu IP" src="docs/screenshots/05-copypastebin-1-1-reguly-wlasne-dokladne-wykluczenia-PL.png" />

### Ostatnie wpisy tylko w pamięci sesji

Osobne okno pokazuje do 15 ostatnio skopiowanych tekstów przechowywanych
wyłącznie w pamięci procesu. Lista znika po zablokowaniu ekranu, wylogowaniu
lub zatrzymaniu rozszerzenia, a przywrócenie wpisu wymaga jawnej akcji. Jest
oddzielona od trwałej historii, która zapisuje ograniczone metadane i HMAC,
lecz nie treść schowka.

<img width="1048" height="721" alt="Historia schowka CopyPasteBin 1.1 z ośmioma syntetycznymi wpisami tekstowymi przechowywanymi wyłącznie w pamięci podręcznej sesji" src="docs/screenshots/07-copypastebin-1-1-tymczasowa-historia-schowka-PL.png" />

</details>

## Zgodność

Wersja 1.2.1 obsługuje następujące środowisko:

| Element | Wymaganie |
| --- | --- |
| System operacyjny | Linux |
| Pulpit | GNOME Shell 50 |
| Serwer wyświetlania | Wayland |
| Python | 3.11 lub nowszy, z modułem `venv` |
| Dodatkowe komponenty | GJS, GTK 4, Libadwaita, GioUnix, GNOME Extensions, `sha256sum` |

Integracje z pulpitami Cinnamon, KDE Plasma i Xfce nie są obsługiwane w wersji
1.2.1. Instalator bezpiecznie zatrzymuje się, jeśli GNOME Shell nie jest
dostępny.

## Instalacja wersji 1.2.1

Wybierz jeden sposób instalacji:

- **Ubuntu 26.04 (Resolute):** użyj stabilnego PPA, aby otrzymywać aktualizacje
  przez APT:

  ```sh
  sudo add-apt-repository ppa:annakozlowska/copypastebin
  sudo apt update
  sudo apt install copypastebin
  ```

  [Otwórz stabilne PPA na Launchpadzie](https://launchpad.net/~annakozlowska/+archive/ubuntu/copypastebin).

- Alternatywnie pobierz trzy pakiety Debiana w dokładnie tej samej wersji:
  `copypastebin-backend`, `gnome-shell-extension-copypastebin` i
  `copypastebin` z [wydania v1.2.1](https://github.com/kozlowska-anna/CopyPasteBin/releases/tag/v1.2.1),
  aby wykonać instalację systemową zarządzaną przez APT.
- [⬇ Pobierz archiwum tar.gz](https://github.com/kozlowska-anna/CopyPasteBin/releases/download/v1.2.1/CopyPasteBin-linux-1.2.1.tar.gz) do instalacji lokalnej bez `sudo`.
- [Pobierz `SHA256SUMS`](https://github.com/kozlowska-anna/CopyPasteBin/releases/download/v1.2.1/SHA256SUMS) i sprawdź wybrane pliki przed ich otwarciem:

```sh
sha256sum --check --ignore-missing SHA256SUMS
```

**Nie łącz instalacji systemowej z PPA/DEB z lokalną instalacją tar.gz.**
Pełną weryfikację, instalację,
aktualizację, zmianę metody oraz odinstalowanie opisuje
[polska instrukcja instalacji](docs/offline-installation.md).

Po rozpakowaniu wariantu lokalnego uruchom kontrolę zgodności, która niczego
nie zmienia:

```sh
./install.sh --check-only
```

Jeżeli kontrola zgłosi `Kontrola zgodności: OK`, zainstaluj CopyPasteBin dla
bieżącego użytkownika:

```sh
./install.sh
```

Instalacja nie wymaga `sudo`, menedżera pakietów ani połączenia z siecią.
Aby aktywować rozszerzenie GNOME Shell, wyloguj się i zaloguj ponownie.
CopyPasteBin powinien uruchomić się automatycznie.

Aby zaktualizować instalację archiwalną, uruchom `./install.sh` z nowej paczki.
Instalacja z PPA otrzymuje aktualizacje przez zwykły mechanizm APT. Ręcznie
zainstalowane pakiety DEB aktualizuj przez APT z trzema nowymi, zgodnymi
plikami. Aktualizacja i usuwanie zachowują prywatną konfigurację użytkownika
oraz trwałe metadane historii wraz z technicznym HMAC, lecz nie sesyjną listę
ostatnio skopiowanych tekstów. Lista ta istnieje wyłącznie w pamięci procesu i
znika po zakończeniu procesu lub sesji.

### Informacje o nowych wersjach

CopyPasteBin nie sprawdza aktualizacji w tle. Nowe wersje są publikowane na
[stronie wydań](https://github.com/kozlowska-anna/CopyPasteBin/releases). Aby
otrzymywać powiadomienia z GitHuba, wybierz w repozytorium
**Watch → Custom → Releases**.

## Prywatność i bezpieczeństwo

CopyPasteBin ogranicza zbędny dostęp oraz ilość przechowywanych danych:

- sprawdzanie schowka i dopasowywanie wzorców odbywa się lokalnie;
- CopyPasteBin nie wysyła treści schowka;
- trwała historia zapisuje metadane i HMAC, ale nie oryginalny ani
  zanonimizowany tekst;
- ostatnie wpisy schowka istnieją tylko w pamięci procesu i są usuwane po
  wyłączeniu rozszerzenia, zablokowaniu ekranu lub zakończeniu sesji;
- tekst między komponentami przechodzi przez ograniczone standardowe wejście i
  wyjście, a nie argumenty poleceń, zmienne środowiskowe, logi lub pliki
  tymczasowe;
- zwykłe wykrywanie nie zmienia schowka;
- zastąpienie schowka wymaga jawnej akcji w edytorze, z wyjątkiem opcjonalnego
  automatycznego czyszczenia, które użytkownik musi najpierw włączyć.

CopyPasteBin nie chroni przed administratorem, innym procesem działającym jako
ten sam użytkownik, menedżerem schowka, obserwacją ekranu ani przejętą aplikacją
źródłową lub docelową. Nie ma gwarancji kryptograficznego wyzerowania pamięci,
na którą mogą także wpływać swap i hibernacja.

Przed użyciem CopyPasteBin w szczególnie wrażliwym procesie przeczytaj
[polski model bezpieczeństwa](docs/security.pl.md) oraz
[kontrakt wersji 1](docs/v1-contract.md).

## Dokumentacja

- [Szczegółowy opis techniczny](docs/technical-overview.pl.md)
- [Roadmapa](ROADMAP.pl.md)
- [Instalacja offline — polski](docs/offline-installation.md)
- [Offline installation — English](docs/offline-installation.en.md)
- [Anonimizacja obrazów](docs/image-redaction.pl.md)
- [Image redaction — English](docs/image-redaction.md)
- [Model bezpieczeństwa — polski](docs/security.pl.md)
- [Security model — English](SECURITY.md)
- [Kontrakt wersji 1 — polski](docs/v1-contract.md)
- [Version 1 contract — English](docs/v1-contract.en.md)
- [Testy wydania 1.2.1 — polski](docs/RELEASE_TESTS_1.2.1.md)
- [Release 1.2.1 test evidence — English](docs/RELEASE_TESTS_1.2.1.en.md)
- [Architektura](docs/architecture.md)
- [Backend zdarzeniowy GNOME](docs/gnome-event-backend.md)
- [Dane stron trzecich](docs/third-party-data.md)
- [Historia zmian — polski](CHANGELOG.md)
- [Changelog — English](CHANGELOG.en.md)

## Rozwój i weryfikacja

Testy automatyczne korzystają z danych syntetycznych i katalogów tymczasowych.
Nie wymagają prawdziwej treści schowka ani prywatnych danych użytkownika.

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 benchmarks/detection_quality.py
PYTHONPATH=src python3 benchmarks/detection_performance.py
PYTHONPATH=src python3 benchmarks/detection_performance.py --minimal-bridge
PYTHONPATH=src python3 benchmarks/persistent_bridge_performance.py
```

Syntetyczny benchmark detekcji zakończył się wynikiem 26/26. Kontrole
automatyczne nie zastępują testu w działającej sesji GNOME Shell. Benchmark
wydajności oddziela czas samego silnika reguł od kosztu uruchomienia procesu,
zapisu filtra i backendowej obsługi zdarzenia przez most GNOME; jego wyniki
zależą od komputera i aktualnego obciążenia systemu. Opcja
`--minimal-bridge` mierzy eksperymentalny, nieaktywny punkt wejścia mostu bez
przełączania na niego rozszerzenia GNOME. Benchmark procesu rezydentnego
sprawdza produkcyjny worker ze stanem syntetycznym w katalogu tymczasowym.
Klient GNOME uruchamia worker leniwie, utrzymuje najwyżej jedno aktywne żądanie
i kończy proces przy pauzie, blokadzie, wyłączeniu rozszerzenia, błędzie albo
po 30 sekundach bezczynności.

## Licencja i autorstwo

Copyright © 2026 Anna Kozłowska.

CopyPasteBin jest udostępniany na licencji
[GNU GPL-3.0-or-later](LICENSE). Informacje i warunki dotyczące danych stron
trzecich znajdują się w pliku [NOTICE](NOTICE).

Projekt powstaje przy wsparciu narzędzi ChatGPT i Codex od OpenAI.
CopyPasteBin jest niezależnym projektem; nie jest powiązany z OpenAI,
zatwierdzony przez OpenAI ani sponsorowany przez OpenAI.
