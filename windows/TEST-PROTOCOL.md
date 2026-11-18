# Etap 0 — protokół ręcznych testów na Windows 11

Cel: zebrać obserwacje o zachowaniu schowka Windows. Nie ma tu wyniku
„zaliczone/niezaliczone" dla systemu — każda obserwacja jest przydatna, także
nieoczekiwana. Jedyne twarde kryteria dotyczą samych narzędzi i są opisane w
sekcji „Kryteria dla narzędzi".

Wyniki wykonanych scenariuszy zapisujemy w [TEST-RESULTS.md](TEST-RESULTS.md).

## Zanim zaczniesz

- Testuj na zwykłym koncie, bez uruchamiania czegokolwiek jako administrator.
- `CpbSyntheticOwner` **nadpisuje schowek**. Zapisz wcześniej wszystko, czego
  potrzebujesz ze schowka.
- W trakcie testów nie kopiuj prawdziwych haseł ani danych. Zamknij menedżer
  haseł. Sonda i tak nie czyta treści, ale sesja testowa ma być syntetyczna.
- Tekst testowy trafi do historii `Win+V`, jeżeli jest włączona. Po testach
  wyczyść ją w Ustawienia → System → Schowek.
- Nie uruchamiaj narzędzi na komputerze z działającą sesją RDP — RDP jest
  osobnym, późniejszym podprotokołem.
- Jeżeli antywirus zablokuje plik `.exe`, nie wyłączaj ochrony. Zapisz
  komunikat w raporcie i przerwij.

Zapisz w raporcie: wydanie i numer kompilacji Windows (`winver`), architekturę
(x64/ARM64), czy historia schowka i synchronizacja między urządzeniami są
włączone.

## Zasady pomiaru

> **Ostrzeżenie: podczas pomiaru nie kopiuj niczego do schowka — ani poleceń,
> ani identyfikatorów testowych (`canary_id`), ani fragmentów wyników.**
> Każde kopiowanie jest zmianą schowka: sonda zarejestruje je jako obce
> zdarzenie, a Windows doda nowy kafelek do historii `Win+V`. Skopiowane
> polecenie zawiera słowa takie jak `--unique-canary` czy `--exclude-monitor`
> i łatwo pomylić je z wynikiem próby; skopiowany identyfikator trafia do
> historii bez flag prywatności i fałszuje wynik.

- Polecenia **wpisuj ręcznie** albo przywołuj z historii PowerShella
  (strzałka w górę, `Ctrl+R`). Nie wklejaj ich z czatu, dokumentu ani notatek.
- Identyfikator z wiersza `canary_id` porównuj z kafelkiem `Win+V` wzrokowo,
  znak po znaku. W notatkach zapisuj tylko wynik porównania („zgodny",
  „brak"), nigdy sam identyfikator.
- W `Win+V` tylko patrz. Kliknięcie kafelka ustawia schowek i tworzy kolejne
  zdarzenie. Kafelki usuwaj dopiero po zatrzymaniu sondy.
- Jedynym wyjątkiem jest kopiowanie wprost przewidziane w scenariuszu (S8:
  tekst `abc` w Notatniku).
- **Sondę uruchamiaj tylko na czas niezbędny do jednej próby** (albo jednej
  opisanej serii prób) i zatrzymuj ją od razu po niej. Każda minuta działania
  sondy to ryzyko zarejestrowania przypadkowej, niezwiązanej zmiany schowka.
  Zmiany schowka między uruchomieniami sondy nie są nigdzie rejestrowane.

## Przygotowanie

Wszystkie polecenia w tym protokole wykonuje się w **PowerShellu** (zwykłe
konto, nie jako administrator) z **jednego katalogu roboczego:
`windows\build`**. Ścieżki do narzędzi zaczynają się od `.\`, a ścieżki do
dziennika od `..\wyniki\`.

Jednorazowo, z katalogu `windows` w repozytorium:

```powershell
cd <repozytorium>\windows
New-Item -ItemType Directory -Force build, wyniki | Out-Null
cd build
..\build.cmd
```

Od tej chwili oba okna pracują w `windows\build`. Okno A — sonda. Okno B —
pozostałe narzędzia. W obu oknach:

```powershell
cd <repozytorium>\windows\build
```

## Przebieg każdej próby (obowiązkowy)

1. **Start sondy** — okno A, nowy plik dziennika z nazwą scenariusza i czasem
   (plik nie może istnieć):

   ```powershell
   $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
   .\CpbClipboardProbe.exe --log "..\wyniki\s01-$stamp.log"
   ```

2. **Próba** — okno B, polecenie scenariusza wpisane ręcznie, zawsze z
   dopiskiem wypisującym kod zakończenia:

   ```powershell
   .\CpbSyntheticOwner.exe; "EXIT=$LASTEXITCODE"
   ```

3. **Zapis EXIT** — zanotuj wartość `EXIT=` dla każdego uruchomienia (także
   wiersze `publish` właściciela, jeśli scenariusz o to prosi — bez wiersza
   `canary_id`). Kody `CpbSyntheticOwner`: `0` — każda transakcja otworzyła
   schowek; `2` — błędne opcje albo plik dziennika; `3` — co najmniej jedna
   transakcja nie otworzyła schowka (próba jest nieważna, a nie negatywna).
   Jeżeli program kończy się przez `Ctrl+C` (S7 — zwolnienie blokady, S8),
   PowerShell może pominąć dopisek po średniku; wtedy od razu po zakończeniu
   programu wpisz osobno `"EXIT=$LASTEXITCODE"`.
4. **Obserwacja** — np. `Win+V`, zgodnie z „Zasadami pomiaru".
5. **Zatrzymanie sondy** — okno A, `Ctrl+C`, od razu po próbie. Nie zamykaj
   okna krzyżykiem: sonda skończy wtedy pracę bez wiersza podsumowania.
6. **Kontrola dziennika** — okno A:

   ```powershell
   Select-String -Path "..\wyniki\s01-$stamp.log" -Pattern 'type=probe_summary', 'type=probe_stop'
   ```

   Muszą się pojawić dokładnie dwa wiersze: `probe_summary` i `probe_stop`.
   Jeżeli ich brak, dziennik jest niezamknięty — opisz to w notatkach.
7. **Klasyfikacja** — w notatkach oznacz dziennik bez publikacji testowej
   (np. po pomyłce w poleceniu) jako nieudane wywołanie, a każde zdarzenie
   `clipboard_update` z `synthetic_fmt=absent` w czasie próby jako obce
   zdarzenie.

W scenariuszach poniżej podano już tylko polecenia z punktu 2 (bez dopisku
`; "EXIT=$LASTEXITCODE"`, który dodaje się zawsze) oraz nietypowe uruchomienia
sondy.

## Scenariusze

### S0. Kompilacja i start

1. `..\build.cmd` — zapisz wszystkie ostrzeżenia i błędy kompilatora.
2. Uruchom sondę bez opcji i od razu zakończ `Ctrl+C`.

Zapisz: czy pojawiło się pytanie UAC (nie powinno), wartości `elevated`,
`listener_registration ok`, `session_registration ok`, czy na pasku zadań
pojawiło się jakiekolwiek okno sondy (nie powinno).

### S1. Jedna transakcja z kilkoma formatami

```powershell
.\CpbSyntheticOwner.exe
```

Zapisz: ile wierszy `clipboard_update` powstało po jednym uruchomieniu oraz
wartości `seq_before` i `seq_after`.

### S2. Wielokrotna identyczna treść

```powershell
.\CpbSyntheticOwner.exe --count 5 --interval-ms 500
```

Zapisz: liczbę zdarzeń i to, czy numer sekwencji rośnie przy identycznej
treści.

### S3. Szybka seria 100 zmian

```powershell
.\CpbSyntheticOwner.exe --count 100 --vary
```

Zapisz: liczbę zdarzeń w sondzie (może być różna od 100), liczbę nieudanych
otwarć z wiersza `probe_summary`.

### S4. Opróżnienie i schowek bez tekstu

```powershell
.\CpbSyntheticOwner.exe --empty-only
.\CpbSyntheticOwner.exe --no-text
```

Zapisz: czy opróżnienie daje zdarzenie i jaką wartość ma `text`.

### S5. Formaty prywatności — poprawne wartości

```powershell
.\CpbSyntheticOwner.exe --exclude-monitor
.\CpbSyntheticOwner.exe --history 0
.\CpbSyntheticOwner.exe --history 1
.\CpbSyntheticOwner.exe --cloud 0
.\CpbSyntheticOwner.exe --cloud 1
.\CpbSyntheticOwner.exe --exclude-monitor --history 0 --cloud 0
```

Po każdym poleceniu naciśnij `Win+V` i zapisz, czy tekst testowy pojawił się w
historii Windows. Zapisz wartości `exclude_monitor`, `history_fmt`,
`history_val`, `cloud_fmt`, `cloud_val`, w tym ewentualny dopisek `_size_gt4`.

### S5c. Unikalny identyfikator a historia `Win+V`

Historia `Win+V` włączona. Sondę w oknie A uruchom z `--log` (katalog
`..\wyniki`). Właściciela w oknie B uruchamiaj **bez** `--log` — jego wyjście
(wiersz `canary_id`) celowo zawiera identyfikator i nie może trafić do
katalogu `wyniki`. Trzy próby, każda z innym automatycznym identyfikatorem:

```powershell
.\CpbSyntheticOwner.exe --unique-canary --history 1 --cloud 0
.\CpbSyntheticOwner.exe --unique-canary --history 0 --cloud 0
.\CpbSyntheticOwner.exe --unique-canary --exclude-monitor --history 0 --cloud 0
```

Dla każdej próby odczytaj wiersz `canary_id` w oknie B, naciśnij `Win+V` i
zapisz, czy kafelek z **dokładnie** tym identyfikatorem się pojawił. Różne
identyfikatory pozwalają przypisać kafelek do konkretnej próby bez czyszczenia
historii między próbami. Ten scenariusz jest szczególnie wrażliwy na
kopiowanie poleceń — patrz „Zasady pomiaru".

Sprzątanie (po zatrzymaniu sondy): usuń prawym przyciskiem tylko kafelki
zaczynające się od `CPB-STAGE0-CANARY-`.

Oczekiwane (do potwierdzenia na Windows, nie dowiedzione statycznie): próba 1
widoczna; próby 2 i 3 nieobecne, jeśli flaga jest honorowana; różnica między
próbą 2 a 3 rozstrzyga, czy potrzebny jest `--exclude-monitor`.

### S5d. Rzeczywisty generator identyfikatorów (po kompilacji, na Windows)

Odpowiednik testu unikalności, który w środowisku chmurowym wykonano jako
ANALOG — tu na skompilowanym kodzie C#. Użyj `--empty-only`, aby nie
publikować tekstu testowego (wiersz `publish` pokaże `text_published=false`
i nic nie trafi do historii `Win+V`). Uwaga: `--empty-only` **opróżnia schowek
i zastępuje jego dotychczasową zawartość**, mimo że nie publikuje tekstu
testowego — zapisz wcześniej to, czego potrzebujesz ze schowka:

```powershell
.\CpbSyntheticOwner.exe --unique-canary --empty-only
.\CpbSyntheticOwner.exe --unique-canary --empty-only
.\CpbSyntheticOwner.exe --unique-canary --empty-only
```

Zapisz trzy wiersze `canary_id value=...`. Potwierdź: (a) każdy pasuje do
`^CPB-STAGE0-CANARY-[0-9A-F]{16}$`, (b) wszystkie trzy są różne. To ćwiczy
rzeczywisty `MakeCanaryId` (GUID → 16 znaków hex → wielkie litery), a nie analog.
Identyfikatorów nie zapisuj w katalogu `wyniki` ani w repozytorium — wystarczy
zanotować wynik (a) i (b).

### S6. Formaty prywatności — wartości uszkodzone

```powershell
.\CpbSyntheticOwner.exe --history bad-value
.\CpbSyntheticOwner.exe --history short
.\CpbSyntheticOwner.exe --cloud bad-value
.\CpbSyntheticOwner.exe --cloud short
```

Zapisz: co raportuje sonda oraz czy Windows dodał wpis do `Win+V`.

Powtórz jedno polecenie z S5 przy sondzie uruchomionej z `--presence-only` i
potwierdź, że `history_val` oraz `cloud_val` mają wtedy wartość `-`:

```powershell
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
.\CpbClipboardProbe.exe --presence-only --log "..\wyniki\s06-presence-$stamp.log"
```

Bez `--unique-canary` każde polecenie publikuje ten sam tekst, więc kafelki
`Win+V` da się przypisać do prób tylko na podstawie czasu. Dodanie
`--unique-canary` do poleceń S6 jest dopuszczalne, ale stanowi **odstępstwo od
pierwotnego protokołu** i trzeba je odnotować w wynikach (tak wykonano S6
18.11.2026 — patrz [TEST-RESULTS.md](TEST-RESULTS.md)).

### S7. Zajęty schowek

Blokada kontrolowana po publikacji — dla 50, 250, 1000 i 5000 ms:

```powershell
.\CpbSyntheticOwner.exe --hold-after-ms 50
```

Najpierw z sondą bez opcji, potem z sondą uruchomioną tak:

```powershell
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
.\CpbClipboardProbe.exe --open-attempts 10 --open-delay-ms 50 --log "..\wyniki\s07b-$stamp.log"
```

Zapisz: `open`, `open_error`, `open_attempts`, `open_time` dla każdego czasu.

Blokada okresowa (inny program stale zajmuje schowek; blokada otwiera się w
osobnym oknie):

```powershell
Start-Process -FilePath .\CpbClipboardBlocker.exe -ArgumentList '--hold-ms', '200', '--count', '100', '--pause-ms', '20'
.\CpbSyntheticOwner.exe --count 10 --interval-ms 300 --vary
```

Zapisz: ile publikacji się powiodło i ile otwarć sondy się nie powiodło.

Zwolnienie po przerwaniu: uruchom `.\CpbClipboardBlocker.exe --hold-ms 60000`,
po kilku sekundach przerwij go `Ctrl+C`, a następnie uruchom
`.\CpbSyntheticOwner.exe`. Zapisz, czy publikacja powiodła się od razu.

### S8. Opóźnione udostępnianie danych

Sonda z opcją `--render-synthetic` (prosi wyłącznie o format syntetyczny):

```powershell
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
.\CpbClipboardProbe.exe --render-synthetic --log "..\wyniki\s08-$stamp.log"
```

W oknie B kolejno, każde zakończ `Ctrl+C` po obejrzeniu wyniku:

```powershell
.\CpbSyntheticOwner.exe --delay-synthetic-ms 0
.\CpbSyntheticOwner.exe --delay-synthetic-ms 1000
.\CpbSyntheticOwner.exe --delay-synthetic-ms 5000
.\CpbSyntheticOwner.exe --delay-synthetic-ms 120000
.\CpbSyntheticOwner.exe --delay-synthetic-ms 1000 --render-nothing
```

Przy wariancie 120000 (właściciel nie odpowiada) w trakcie oczekiwania skopiuj
w Notatniku dowolny tekst testowy, np. `abc` (to jedyne kopiowanie przewidziane
w protokole).

Zapisz: `synthetic_render` (wynik, kod błędu, przedział czasu), po jakim czasie
sonda odzyskała sterowność, czy zdarzenia z czasu blokady pojawiły się później
i w jakiej liczbie, jak zachowały się numery sekwencji.

Następnie przy sondzie **bez** `--render-synthetic`:

```powershell
.\CpbSyntheticOwner.exe --delay-text-ms 2000 --stay-seconds 60
```

Zapisz: wartość `text` w sondzie oraz to, czy w oknie B pojawił się wiersz
`render_request format=text`, mimo że sonda o tekst nie prosi. Jeżeli tak,
tekstu zażądał inny składnik systemu (np. historia `Win+V`) — zanotuj, przy
jakich ustawieniach historii to wystąpiło.

### S9. Zdarzenia sesji i zasilania

Sonda musi zapisywać do pliku (`--log`). Dla każdego kroku osobny plik. To
jedyny scenariusz, w którym sonda działa dłużej niż pojedyncza próba — tylko
przez czas danego kroku.

1. `Win+L`, odczekaj 10 s, odblokuj.
2. `Win+L`; przed zablokowaniem uruchom w oknie B
   `.\CpbSyntheticOwner.exe --count 20 --interval-ms 2000 --vary`, tak aby
   publikacje trwały podczas blokady; odblokuj po 20 s.
3. Uśpienie komputera i wznowienie.
4. Przełączenie użytkownika (jeżeli istnieje drugie konto) i powrót.
5. Wylogowanie przy działającej sondzie; po ponownym zalogowaniu otwórz plik.

Zapisz: które wiersze `session`, `power`, `query_end_session`, `end_session`
się pojawiły; czy podczas blokady wiersze `clipboard_update` miały
`gate=locked` i nie zawierały pól `text`, `open`; wartość
`other_session_events_ignored`; czy przy wylogowaniu zdążył zapisać się
`end_session` i `probe_summary`.

### S10. RDP

Poza zakresem tej tury. Nie wykonuj.

### S11. Historia i synchronizacja Windows

Powtórz S1 i pierwsze trzy polecenia S5 w konfiguracjach: historia wyłączona;
historia włączona; historia i synchronizacja włączone (tylko jeśli już ich
używasz — nie włączaj synchronizacji specjalnie do testu).

Zapisz: czy liczba zdarzeń, numery sekwencji lub żądania `render_request`
różnią się między konfiguracjami.

### S12. Uprawnienia

Potwierdź, że wszystkie powyższe kroki działały na zwykłym koncie, z
`elevated=false`, bez pytań UAC i bez instalowania czegokolwiek.

## Kryteria dla narzędzi

Te warunki muszą być spełnione; każde odstępstwo to błąd narzędzia do
zgłoszenia:

1. Tekst kontrolny nie występuje w żadnym dzienniku **sondy** (z
   `windows\build`):

   ```powershell
   Select-String -Path ..\wyniki\*.log -SimpleMatch 'CPB-STAGE0-CANARY'
   ```

   Polecenie nie może niczego znaleźć. Uwaga: wyjście **właściciela** (wiersz
   `canary_id` przy `--unique-canary`) celowo zawiera identyfikator oparty na
   tekście kontrolnym — dlatego właściciela w S5c uruchamia się bez `--log`, a
   katalog `wyniki` zawiera wyłącznie logi sondy. Kryterium dotyczy tych logów.
2. Żaden wiersz sondy nie zawiera treści, długości treści, nazwy programu,
   PID ani tytułu okna.
3. Podczas blokady sesji sonda nie wypisuje pól `text`, `open` ani wartości
   formatów.
4. Sonda nie zmienia zawartości schowka (po jej uruchomieniu i zakończeniu
   `Ctrl+V` wkleja to samo co wcześniej).
5. Sonda nie wymaga administratora i nie pokazuje okna.
6. `--log` odmawia użycia istniejącego pliku.

## Co odesłać

- komunikaty kompilatora z S0;
- pliki z katalogu `wyniki` (zawierają wyłącznie metadane — przejrzyj je przed
  wysłaniem); **nie dodawaj ich do repozytorium**;
- notatki z pól „Zapisz" dla każdego scenariusza, z wartościami `EXIT=`;
- wersję Windows i ustawienia historii schowka;
- wszystko, co wyglądało na zawieszenie, błąd albo zaskoczenie.

Do repozytorium trafia wyłącznie podsumowanie w
[TEST-RESULTS.md](TEST-RESULTS.md) — bez dzienników, bez identyfikatorów
testowych i bez plików `.exe`.

Nie dołączaj zrzutów ekranu z historią `Win+V`, jeżeli widać na nich cokolwiek
poza tekstem testowym.

## Po testach

- Wyczyść historię schowka Windows.
- Usuń katalogi `windows\build` i `windows\wyniki`, jeśli nie są już potrzebne.
  Narzędzia nie zostawiają niczego poza nimi: nie zapisują ustawień, nie
  dodają autostartu i nie działają po zamknięciu okna.
