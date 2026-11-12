# CopyPasteBin dla Windows — etap 0 (eksperyment)

Ten katalog **nie jest wersją CopyPasteBin dla Windows**. Zawiera trzy małe
narzędzia testowe, które mają odpowiedzieć na pytania o zachowanie schowka
Windows, zanim zapadnie jakakolwiek decyzja o architekturze produkcyjnej.
Narzędzia nie wykrywają danych wrażliwych, nie ostrzegają i niczego nie
chronią.

Stan: kod został napisany w kontenerze Linux i **nigdy nie był kompilowany ani
uruchamiany na Windows**. Pierwsza kompilacja i wszystkie testy odbywają się
ręcznie według [TEST-PROTOCOL.md](TEST-PROTOCOL.md).

## Co zawiera katalog

| Plik | Rola |
|---|---|
| `src/ClipboardProbe.cs` | sonda metadanych schowka (`CpbClipboardProbe.exe`) |
| `src/SyntheticOwner.cs` | syntetyczny właściciel schowka (`CpbSyntheticOwner.exe`) |
| `src/ClipboardBlocker.cs` | program blokujący schowek (`CpbClipboardBlocker.exe`) |
| `src/Native.cs` | pełna, zamknięta lista używanych funkcji systemowych |
| `src/Common.cs` | wspólny zapis wierszy metadanych i obsługa opcji |
| `build.cmd` | kompilacja kompilatorem wbudowanym w Windows |
| `checks/test_stage0_sources.py` | statyczne kontrole źródeł (dowolny system) |
| `TEST-PROTOCOL.md` | protokół ręcznych testów na Windows 11 |

## Granice sondy

Sonda zapisuje wyłącznie:

- względny czas od startu (`t`) i numer porządkowy wiersza (`n`);
- typ zdarzenia: zmiana schowka, zdarzenie sesji, zasilania, zakończenia sesji;
- numer sekwencji schowka przed obsługą zdarzenia i po niej;
- wynik `OpenClipboard`: powodzenie, kod błędu, liczbę prób i przedział czasu;
- czy dostępny jest tekst (`text=true/false`), bez pobierania go;
- obecność trzech znanych formatów prywatności i jednego formatu syntetycznego;
- dla `CanIncludeInClipboardHistory` i `CanUploadToCloudClipboard`: `0`, `1`
  albo stan nieprawidłowy (nieprawidłowa wartość nie jest wypisywana);
- stan rejestracji nasłuchu i powiadomień sesji;
- informację, czy proces działa z podwyższonymi uprawnieniami.

Sonda nigdy:

- nie wywołuje `GetClipboardData` dla tekstu, więc nie czyta treści, długości
  ani skrótu treści;
- nie wylicza listy formatów schowka;
- nie ustala właściciela schowka, PID, nazwy procesu ani tytułu okna;
- nie zapisuje niczego do schowka i go nie opróżnia;
- nie używa sieci, rejestru ani telemetrii;
- nie nadpisuje istniejącego pliku (`--log` tworzy wyłącznie nowy plik);
- nie otwiera schowka i nie sprawdza formatów, gdy sesja jest zablokowana.

Jedyne dane pobierane ze schowka to dwie czterobajtowe flagi prywatności oraz,
tylko po podaniu `--render-synthetic`, uchwyt do formatu syntetycznego
`CopyPasteBin.Stage0.SyntheticFormat`. Ten format publikuje wyłącznie
`CpbSyntheticOwner`; sonda mierzy czas oczekiwania i nie odczytuje pamięci pod
uchwytem. Opcja `--presence-only` wyłącza także odczyt wartości flag.

Do własnego użytku sonda pobiera identyfikator swojej sesji, aby pominąć
zdarzenia innych sesji. Nie wypisuje go.

## Pozostałe dwa narzędzia

`CpbSyntheticOwner` **zastępuje zawartość schowka** stałym tekstem testowym
zaczynającym się od `CPB-STAGE0-CANARY` i nie czyta poprzedniej zawartości.
Potrafi dodać formaty prywatności (także z uszkodzoną wartością), opóźnić
udostępnienie danych i przytrzymać schowek po publikacji.
Opcja `--unique-canary` nadaje każdemu uruchomieniu niesekretny, unikalny
identyfikator tekstu testowego (np. `CPB-STAGE0-CANARY-A1B2C3D4E5F60718`),
widoczny jako wiersz `canary_id` w wynikach właściciela; sonda tekstu nie
czyta, więc go nie zna. Wiersz `publish` raportuje `text_published`
odzwierciedlające rzeczywisty wynik `SetClipboardData`: `false` przy
`--empty-only`, `--no-text`, niepowodzeniu publikacji oraz dla samej zapowiedzi
opóźnionego renderowania (faktyczne udostępnienie danych widać osobno jako
`render_result`).

`CpbClipboardBlocker` otwiera schowek, trzyma go przez zadany czas i zamyka.
Nie czyta i nie zmienia zawartości.

Każde narzędzie pokazuje opcje po uruchomieniu z `--help`.

## Kompilacja

Wymagania: Windows 11, zwykłe konto użytkownika. Nie trzeba niczego instalować
ani pobierać — skrypt używa kompilatora C# z .NET Framework 4.x, który jest
składnikiem systemu.

1. Pobierz repozytorium na komputer z Windows (gałąź `claude-windows`).
2. Otwórz „Wiersz polecenia" (nie jako administrator) w katalogu `windows`.
3. Uruchom:

   ```bat
   build.cmd
   ```

4. Pliki `.exe` pojawią się w `windows\build`. Katalog `build` jest ignorowany
   przez Git.

Jeżeli kompilator zgłosi błąd lub ostrzeżenie, skopiuj komunikaty do raportu z
testów i nie poprawiaj kodu ręcznie — to informacja potrzebna do naprawy.

Wybór wbudowanego kompilatora dotyczy tylko tych narzędzi testowych. Nie
przesądza technologii wersji produkcyjnej.

## Uruchomienie

Sondę uruchamia się w osobnym oknie wiersza polecenia i zostawia włączoną:

```bat
build\CpbClipboardProbe.exe --log wyniki\sonda-01.log
```

Katalog `wyniki` trzeba wcześniej utworzyć, a plik nie może istnieć. Sondę
kończy `Ctrl+C`. Zamknięcie okna krzyżykiem kończy ją bez wiersza
podsumowania.

Przykładowy wiersz:

```text
t=12.345 n=7 type=clipboard_update seq_before=101 gate=open text=true exclude_monitor=absent history_fmt=present cloud_fmt=absent synthetic_fmt=present open=ok open_error=0 open_attempts=1 open_time=lt1ms history_val=0 cloud_val=- synthetic_render=- seq_after=101
```

## Kontrole dostępne bez Windows

```bash
python3 -B -m unittest discover -s windows/checks -v
```

Kontrole sprawdzają tekst źródeł: zamkniętą listę funkcji systemowych, brak
odczytu tekstu, brak identyfikacji programów, brak sieci, obecność tekstu
kontrolnego tylko w syntetycznym właścicielu. Nie potwierdzają, że kod się
kompiluje ani że działa poprawnie na Windows.

## Znane ograniczenia etapu 0

- Sonda obsługuje wszystko w jednym wątku. Nie pozwala więc jeszcze porównać
  modelu „osobny wątek" z modelem „proces pomocniczy"; pokazuje tylko, jak
  długo trwa blokada i czy zdarzenia się kolejkują.
- Bramka blokady reaguje na `lock` i `unlock`. Pozostałe zdarzenia sesji są
  tylko rejestrowane; polityka dla nich nie jest ustalona.
- Wyścig między zdarzeniem schowka a blokadą sesji nie jest tu badany.
- Sonda nie sprawdza ustawień historii schowka Windows (`Win+V`) ani jej
  zawartości; ich stan zapisuje ręcznie osoba testująca.
