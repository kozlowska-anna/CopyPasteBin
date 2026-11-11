# CopyPasteBin 1.3-dev — test LIVE skrótu na Ubuntu

Data: 2026-11-11
Status: pierwsza seria LIVE zakończona; poprawki wymagają ponownego testu

## Środowisko i artefakt

Test użytkowniczki wykonano na komputerze Dell z Ubuntu 26.04.1 LTS, GNOME
Shell 50.1, Waylandem i Pythonem 3.14.4. Użyto lokalnego instalatora bez
`sudo`, z artefaktu zbudowanego z commita
`987e85a3802a97e2d1fbd0977cbcb867fe233d1f`, SHA-256
`44d4982b11df8ddeccab0bc5e7d7655a201e181594e529dbb2a00bc82b00e363`.

W raporcie nie zapisano nazwy konta ani hosta, ponieważ nie są potrzebne do
odtworzenia testu.

## Wyniki

- weryfikacja sumy, `--check-only`, instalacja lokalna i załadowanie
  rozszerzenia: PASS;
- ikona, menu, konfiguracja `Super+Shift+E`, otwieranie jednego edytora,
  autorepeat, cleanup skrótu, blokada ekranu, pauza i wznowienie: PASS;
- przywołanie już otwartego edytora: FAIL — GTK zgłaszało prezentację, ale
  Mutter pozostawiał okno w tle i pokazywał żądanie uwagi;
- e-mail zakończony kropką zdaniową: FAIL; przecinek, średnik i dwukropek: PASS;
- pełny konflikt z innym skrótem, wszystkie scenariusze historii i pełny test
  anonimizacji obrazów nie zostały zakończone.

Globalne `org.gnome.shell disable-user-extensions=true` blokowało wszystkie
rozszerzenia użytkownika mimo prawidłowego wpisu UUID na liście włączonych.
Nie był to błąd aktywacji CopyPasteBin.

## Diagnoza i poprawki

1. `f637b6c` poprawia granicę dopasowania e-maila. Błąd występował bezpośrednio
   w detektorze, przed walidacją mostu, historią, deduplikacją i banerem.
   Końcowa kropka pozostaje poza zakresem wykrycia, a kontynuacja domeny po
   kropce nadal jest odrzucana. Zmieniono wersję reguł z 10 na 11.
2. `b84db7a` zachowuje lokalny sygnał GTK, ale aktywuje dokładnie okno o GTK
   application ID edytora przez GNOME Shell w reakcji na jawną akcję
   użytkowniczki. Po krótkim opóźnieniu sprawdzany jest rzeczywisty fokus.
   Baner sukcesu pozostaje; niepowodzenie ma osobny, prawdziwy komunikat.
3. `b8fa43d` dodaje wyłącznie odczyt i ostrzeżenie o
   `disable-user-extensions=true`. Instalator nie zmienia globalnego ustawienia.

Poprawka e-maila jest niezależnym kandydatem do backportu bezpieczeństwa do
stabilnej linii, ale nie została tam przeniesiona ani opublikowana.

## Weryfikacja automatyczna

Po poprawkach pełne polecenie źródłowe:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
python3 -m unittest discover -s tests -q
```

zakończyło się wynikiem `397/397 PASS`. Cztery testy dekodowania obrazów,
wcześniej blokowane przez Glycin/D-Bus, przeszły w tym przebiegu. Nie osłabiono
testów ani izolacji.

## Pauza i przyszłe dyktowanie

Obecna pauza nadal blokuje edytor czytający schowek i nie została zmieniona.
Projekt STT powinien rozróżnić dwa jawne tryby otwarcia edytora:

- `clipboard` — odczytuje schowek i respektuje obecną bramkę pauzy;
- `blank` — otwiera pusty bufor bez odczytu schowka i może działać podczas
  pauzy monitoringu.

Dyktowanie w trybie `blank` nie może automatycznie wznowić monitoringu ani
zapisać tekstu do schowka. Implementacja tego podziału wymaga osobnej decyzji.

## Zakres ponownego testu LIVE

Następna paczka powinna sprawdzić przede wszystkim e-mail zakończony kropką,
rzeczywiste przywołanie edytora, prawdziwy komunikat błędu aktywacji oraz
ostrzeżenie instalatora o globalnej blokadzie rozszerzeń. Pozostałe funkcje
należy objąć krótką regresją na danych syntetycznych.
