# Roadmapa CopyPasteBin

[English](ROADMAP.md) | **Polski**

Roadmapa pokazuje kierunek rozwoju CopyPasteBin bez zamieniania wczesnych
pomysłów w obietnice wydania. Nie zawiera sztywnych terminów. Priorytety mogą
się zmieniać po testach, uwagach użytkowników, przeglądzie bezpieczeństwa albo
zmianach w obsługiwanych środowiskach graficznych.

## Tożsamość produktu i zasada rozwoju

CopyPasteBin jest menedżerem schowka skoncentrowanym na prywatności, a nie
narzędziem do archiwizowania wszystkiego. Rozwój powinien wzmacniać trzy
codzienne zadania: zauważenie ryzyka po skopiowaniu treści, przygotowanie lub
anonimizację materiału oraz świadomą decyzję, co ostatecznie wkleić.

Obowiązuje zasada: **przechowuj jak najmniej, analizuj tylko tyle, ile potrzeba,
oddawaj decyzję użytkownikowi**. Nowe funkcje nie powinny zmieniać CPB w
rozbudowane, trwałe archiwum schowka.

## Znaczenie statusów

- **W realizacji** — zatwierdzona praca, która jest obecnie przygotowywana lub
  testowana.
- **Planowane** — zaakceptowany kierunek, ale nie obietnica konkretnej wersji
  ani terminu.
- **Badamy** — możliwość na etapie rozpoznania. Może się istotnie zmienić albo
  w ogóle nie wejść do programu.
- **Nie planujemy** — świadoma granica produktu, dopóki właścicielka jawnie jej
  nie zmieni.

## Aktualne wydanie publiczne

CopyPasteBin 1.1 jest obecnym publicznym wydaniem stabilnym. Zapewnia lokalne
wykrywanie danych wrażliwych, ostrzeżenia, anonimizację tekstu, dokładne
wykluczenia niskiego i średniego ryzyka, Bezpieczne wklejenie, pauzę oraz
ostatnie teksty schowka przechowywane tylko w pamięci sesji GNOME Shell 50 na
Waylandzie. Wersja 1.1 dodaje ręczną, lokalną anonimizację obrazów PNG/JPEG,
odświeżone ikony aplikacji i panelu, poprawione sterowanie pauzą oraz dwa
formaty instalacji z tego samego zestawu źródeł: pakiet Debiana i lokalne dla
użytkownika archiwum tar.gz.

## Planowane

### Wygodniejsze przygotowanie tekstu

Planowane jest rozwijanie podręcznego edytora i reguł własnych, w tym możliwość
użycia wyrażeń regularnych po zaprojektowaniu bezpiecznych limitów i czytelnego
przeglądu dopasowań. Celem jest łatwiejsze przygotowanie treści, a nie
automatyczne podejmowanie decyzji za użytkowniczkę.

### Udoskonalanie ręcznej anonimizacji obrazów

Po wersji 1.1 ręczny przepływ anonimizacji obrazów może być udoskonalany na
podstawie rzeczywistego użycia. Podstawowa granica pozostaje niezmienna:
użytkowniczka wybiera lokalny obraz, wskazuje obszary do zakrycia i zapisuje
nowy plik bez modyfikowania oryginału.

## Badamy

### Jawne lokalne OCR

CopyPasteBin może zbadać uruchamiany na żądanie, wyłącznie lokalny etap OCR do
przeglądania tekstu w obrazie wybranym przez użytkowniczkę. Ta funkcja nie jest
zaimplementowana. Wymagałaby jawnej akcji i przeglądu; nie monitorowałaby po
cichu obrazów ani nie wykonywałaby automatycznej anonimizacji.

### Dodatkowe środowiska graficzne

Linux Mint Cinnamon i KDE Plasma wymagają osobnych adapterów pulpitu oraz
rzeczywistych testów. Obecność rdzenia CLI nie potwierdza zgodności z danym
środowiskiem. W przypadku KDE należałoby oddzielnie ocenić Wayland i X11.

### Windows

Wersja Windows jest kierunkiem badawczym, a nie zapowiedzianym portem ani
wydaniem z ustalonym terminem.

### Dystrybucja i warianty pracy

Możliwe przyszłe prace obejmują standardowe źródłowe pakowanie Debiana,
metadane copyright DEP-5, podpisane repozytorium pakietów, opcjonalne profile
filtrów albo oddzielenie rdzenia detekcji od integracji właściwych dla pulpitu.
Każda z tych możliwości wymaga konkretnej korzyści dla użytkowników, zanim
zwiększy zakres produktu lub koszt jego utrzymania.

## Nie planujemy

Obecny kierunek produktu nie obejmuje:

- przetwarzania w chmurze, kont, synchronizacji, telemetrii ani reklam;
- trwałego przechowywania treści schowka;
- niejawnego zastępowania tekstu schowka w tle;
- przejmowania zwykłego `Ctrl+V`, automatycznego wklejania ani globalnych
  hooków wejścia;
- sprawdzania aplikacji, pola, okna lub adresu URL będącego celem wklejenia;
- przywracania dawnego pollingowego watchera ani instalowania niepotrzebnej,
  stale działającej usługi.

CopyPasteBin zachowuje zasadę: **sugestia może być automatyczna, wykonanie
nie**. Zapis zanonimizowanej treści albo zmiana konfiguracji wymagają jawnej
decyzji użytkowniczki.

## Uwagi i propozycje

Publiczne zgłoszenia mogą służyć do rozmowy o priorytetach, ale nie należy do
nich dołączać prawdziwych sekretów, prywatnej treści schowka, prywatnych
obrazów ani konfiguracji produkcyjnej. Pozycje roadmapy opisują kierunek, a nie
gwarancję wdrożenia funkcji.
