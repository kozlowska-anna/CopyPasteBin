# CopyPasteBin 1.3 — modele STT pobierane na żądanie

Status: zatwierdzona architektura i walidowany manifest; downloader i GUI nie
są jeszcze zaimplementowane.
Data: 2026-11-12

## Decyzja produktu

Model STT jest opcjonalnym składnikiem danych, niezależnym od instalacji CPB i
wersji silnika. Aplikacja nie pobiera modelu przy starcie ani aktualizacji.
Pobieranie rozpoczyna wyłącznie świadome kliknięcie **Pobierz**, po pokazaniu
źródła, licencji, rozmiaru pobrania i wymaganego miejsca. Zainstalowany model
działa offline i można go usunąć bez odinstalowywania CPB. Brak modelu wyłącza
tylko dyktowanie, nie ochronę schowka ani historię.

## Architektura

```text
ustawienia dyktowania (GJS / GTK 4, bez sieci)
  -> identyfikator modelu z wbudowanego katalogu
  -> osobny downloader (sieć, bez mikrofonu i schowka)
  -> prywatny plik częściowy + limit rozmiaru + SHA-256
  -> atomowa instalacja w katalogu modeli

edytor -> worker STT (model tylko do odczytu, audio tylko w aktywnej sesji,
                       osobna przestrzeń sieciowa bez internetu)
```

GUI przekazuje downloaderowi wyłącznie zamknięty identyfikator modelu, nigdy
URL, sumę ani ścieżkę. Downloader ponownie odczytuje manifest dołączony do
wydania CPB. Silnik i model mają niezależne wersje, a manifest deklaruje
zamkniętą listę zgodnych wersji silnika.

## Manifest i polityka integralności

`src/copypastebin/data/stt-models-v1.json` jest wersjonowaną allowlistą. Wpis
zawiera nazwy PL/EN, język, wersję modelu, zgodne wersje silnika, HTTPS URL,
dokładny rozmiar, wymagane miejsce, SHA-256, format, licencję, względną ścieżkę
instalacji i orientacyjny RAM. Model bez wiarygodnego dowodu integralności ma
`download.enabled=false` oraz publiczny opis ograniczenia zamiast sumy.

Parser odrzuca dodatkowe pola, HTTP, URL-e z danymi logowania, duplikaty,
nieznane formaty, błędne sumy i rozmiary, ścieżki absolutne, `..`, backslashe
oraz symlinkowany manifest.

Whisper tiny ma niezmienny commit źródła, dokładny rozmiar i opublikowaną sumę
SHA-256. Vosk `small-pl-0.22` jest widoczny jako kandydat zgodny z Vosk 0.3.45,
ale przycisk **Pobierz** pozostaje nieaktywny. Upstream nie publikuje
niezależnie sprawdzalnej sumy, a hash obliczony po pierwszym pobraniu w C4 nie
jest dowodem autentyczności. Włączenie wymaga wiarygodnej sumy upstream,
podpisanego manifestu albo osobno zatwierdzonego kanału dystrybucji.

## Lokalizacja i cykl życia

```text
${XDG_DATA_HOME:-$HOME/.local/share}/copypastebin/models/
  .incoming/<losowy-token>/
  <silnik>/<wersja-silnika>/<model>/
```

Katalogi mają tryb `0700`, a pliki `0600`. Przyszły downloader tworzy plik
częściowy na docelowym systemie plików przez `O_EXCL|O_NOFOLLOW`, sprawdza
miejsce, ogranicza liczbę bajtów niezależnie od HTTP, wymaga HTTPS na każdym
dozwolonym przekierowaniu, sprawdza rozmiar i SHA-256, wykonuje `fsync` i
atomowe `rename`. Dla archiwów dodatkowo odrzuca ścieżki absolutne, `..`,
backslashe, urządzenia, dowiązania i przekroczenie limitu po rozpakowaniu.

Działający model pozostaje dostępny, dopóki zamiennik nie przejdzie pełnej
weryfikacji. Anulowanie lub awaria usuwa tylko plik częściowy konkretnej
operacji. Sprzątanie nie uruchamia sieci i odrzuca symlinki oraz obiekty o
niewłaściwym właścicielu lub trybie.

Usunięcie wymaga potwierdzenia. Backend przyjmuje identyfikator z manifestu,
wyznacza ścieżkę pod katalogiem modeli i nie podąża za symlinkami. Model
używany przez aktywną sesję nie może zostać usunięty.

## GTK 4

Sekcja **Modele językowe** pokazuje nazwę, język, rozmiar pobrania, wymagane
miejsce, RAM, licencję, źródło i zgodny silnik. Zamknięte stany to:

- `not-installed` — **Pobierz**;
- `downloading` — postęp i **Anuluj pobieranie**;
- `ready` — **Wybierz** i **Usuń**;
- `error` — publiczny komunikat bez danych oraz ponowienie;
- `unavailable` — brak pobierania i jawne ograniczenie integralności.

Przed pobraniem pojawia się potwierdzenie ze źródłem, licencją i rozmiarami.
Zamknięcie okna nie zmienia operacji w ukryte pobieranie: użytkownik potwierdza
anulowanie albo okno pozostaje widoczne. Status **Gotowy** pojawia się dopiero
po weryfikacji i atomowej instalacji. **Wybierz** wymaga zgodnego silnika. Nie
ma automatycznych aktualizacji.

Przy braku modelu kontrolka mikrofonu wyjaśnia problem i prowadzi do ustawień.
Nie zmienia stanu ochrony schowka.

## Uprawnienia i izolacja

| Komponent | Otrzymuje | Nie otrzymuje |
| --- | --- | --- |
| katalog/GUI | publiczny manifest i status | sieć, mikrofon, schowek, zapis modelu |
| downloader | sieć po potwierdzeniu; zapis `.incoming` i modelu | mikrofon, audio, historia, schowek, `sudo` |
| worker STT | model tylko do odczytu, aktywny strumień audio, ograniczony pipe | sieć, zapis modelu, historia, schowek |

Worker STT działa przez `bwrap --unshare-net` bez szerokiego bindu `/`.
Otrzymuje tylko biblioteki, konkretny silnik i model, ograniczone IPC, potrzebne
`/proc` oraz pusty `/tmp`. Produkcja doda wyłącznie wybrane wejście audio na
czas jawnej sesji. Sama flaga `offline=true` nie dowodzi izolacji.

Downloader jest osobnym procesem z siecią, ale bez urządzeń audio oraz bez
konfiguracji, historii i schowka CPB. HTTPS i SHA-256 chronią artefakt;
allowlista hostów oraz limit przekierowań ograniczają klienta. Dokładna
polityka przekierowań CDN wymaga zatwierdzenia przed implementacją sieciową.

## Główne ryzyka

| Ryzyko | Zabezpieczenie |
| --- | --- |
| podmiana lub ucięcie modelu | przypięty URL, dokładny rozmiar i SHA-256 |
| zip bomb / path traversal | limity oraz walidacja każdego wpisu |
| zapis poza katalogiem | identyfikator zamiast ścieżki, `O_NOFOLLOW`, ścieżka z manifestu |
| awaria lub brak miejsca | rezerwa, prywatny plik częściowy, atomowa publikacja |
| sieć podczas STT | osobna przestrzeń sieciowa inferencji |
| usunięcie aktywnego modelu | blokada sesji i potwierdzenie |
| fałszywa autentyczność Vosk | pobieranie zablokowane do uzyskania niezależnego dowodu |
| niezgodność modelu i silnika | macierz wersji sprawdzana przy wyborze i starcie |

## Zakres 1.3 i stan implementacji

Bez opóźniania benchmarku można utrzymać obecny manifest, parser i testy. Nie
mają sieci, zależności ani wpływu na stabilne CPB. Kolejność pozostaje:

1. adapter `whisper-cli`, zatwierdzony korpus i benchmark Vosk/Whisper;
2. wybór obsługiwanego silnika i modelu na podstawie pomiarów;
3. małe GUI oraz downloader pojedynczego pliku dla wybranych pozycji;
4. testy anulowania, braku miejsca, awarii, przekierowań i atomowej instalacji;
5. archiwa i ewentualny Vosk dopiero po rozwiązaniu integralności.

Zaimplementowano: manifest v1, osobne wersje silnika/modelu, zgodność wersji,
parser bez sieci, lokalną kontrolę rozmiaru/SHA-256, odrzucanie symlinków i
testy na fikcyjnym modelu. Nie zaimplementowano HTTP, GUI, postępu, anulowania,
instalacji, usuwania, rozpakowywania ani aktualizacji. Nowy mechanizm nie pobrał
żadnego rzeczywistego modelu.
