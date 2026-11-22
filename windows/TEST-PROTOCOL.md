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

Scenariusz mierzy, co sonda rejestruje, gdy schowek jest zajęty przez inny
program. W trakcie S7 schowek bywa niedostępny dla wszystkich programów (do
5 s naraz), a każde uruchomienie właściciela zastępuje jego zawartość — zapisz
wcześniej to, czego potrzebujesz. Nie kopiuj niczego i nie blokuj ekranu.
Właściciela uruchamiaj bez `--unique-canary` i bez `--log`.

Dwie konfiguracje sondy (okno A); każda próba to osobne uruchomienie sondy i
osobny dziennik. Przed startem sondy wpisz przypisanie `$proba` z kolumny
„Okno A" w tabeli poniżej — to jedyna wartość, która zmienia się między
próbami. Przykład dla próby 2 (sonda domyślna, blokada 50 ms):

```powershell
$proba = 'h50'
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
.\CpbClipboardProbe.exe --log "..\wyniki\s07-$proba-$stamp.log"
```

Przykład dla próby 3 (sonda z ponawianiem: do 10 prób co 50 ms, ta sama
blokada 50 ms):

```powershell
$proba = 'h50'
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
.\CpbClipboardProbe.exe --open-attempts 10 --open-delay-ms 50 --log "..\wyniki\s07b-$proba-$stamp.log"
```

Dziennik sondy domyślnej zaczyna się od `s07-`, sondy z ponawianiem od
`s07b-`. Krok 6 „Przebiegu każdej próby" wykonuj z tą samą nazwą pliku, np.
`Select-String -Path "..\wyniki\s07-$proba-$stamp.log" -Pattern
'type=probe_summary', 'type=probe_stop'` (dla sondy z ponawianiem: `s07b-`).

#### Kolejność prób

Próby wykonuj w tej kolejności. Dla każdego czasu blokady najpierw sonda
domyślna, potem sonda z ponawianiem (przeplatanie — **odstępstwo od
pierwotnego protokołu**, przyjęte 18.11.2026, do odnotowania w wynikach).

| Nr | Okno A | Sonda (dziennik) | Polecenie w oknie B |
|---|---|---|---|
| 1 | `$proba = 'k0'` (kontrola bez blokady) | domyślna (`s07-`) | `.\CpbSyntheticOwner.exe` — trzy razy, w odstępach kilku sekund, w jednym uruchomieniu sondy |
| 2 | `$proba = 'h50'` | domyślna (`s07-`) | `.\CpbSyntheticOwner.exe --hold-after-ms 50` |
| 3 | `$proba = 'h50'` | z ponawianiem (`s07b-`) | `.\CpbSyntheticOwner.exe --hold-after-ms 50` |
| 4 | `$proba = 'h250'` | domyślna (`s07-`) | `.\CpbSyntheticOwner.exe --hold-after-ms 250` |
| 5 | `$proba = 'h250'` | z ponawianiem (`s07b-`) | `.\CpbSyntheticOwner.exe --hold-after-ms 250` |
| 6 | `$proba = 'int'` (zwolnienie po przerwaniu) | domyślna (`s07-`) | patrz „Próba przerwania blokady" |
| 7 | `$proba = 'h1000'` | domyślna (`s07-`) | `.\CpbSyntheticOwner.exe --hold-after-ms 1000` |
| 8 | `$proba = 'h1000'` | z ponawianiem (`s07b-`) | `.\CpbSyntheticOwner.exe --hold-after-ms 1000` |
| 9 | `$proba = 'h5000'` | domyślna (`s07-`) | `.\CpbSyntheticOwner.exe --hold-after-ms 5000` |
| 10 | `$proba = 'h5000'` | z ponawianiem (`s07b-`) | `.\CpbSyntheticOwner.exe --hold-after-ms 5000` |
| 11 | `$proba = 'per25'` (blokada okresowa) | domyślna (`s07-`) | patrz „Blokada okresowa" |
| 12 | `$proba = 'per100'` (opcjonalnie) | domyślna (`s07-`) | jak 11, ale `'--count', '100'` — tylko jeśli próba 11 nie wystarczy do oceny |

Próby 2–5 i 7–10 nazywane są dalej **próbami z blokadą właściciela**.

Próba 6 sprawdza mechanizm awaryjny (zwolnienie schowka przez Windows po
przerwaniu programu), dlatego wykonuje się ją **przed** dłuższymi blokadami.
Jeżeli próba 6 jest nieważna albo po niej schowek pozostaje zajęty, przerwij
S7 i nie wykonuj prób 7–12.

#### Co zapisać po każdej próbie

- z okna B: `EXIT=` każdego uruchomienia oraz z wiersza `publish` właściciela
  wartości `open`, `text`, `text_published`, `hold_after` (i ewentualnie
  `hold_after_error`) oraz `seq`;
- z dziennika sondy, dla zdarzenia z `synthetic_fmt=present`: `open`,
  `open_error`, `open_attempts`, `open_time`, `seq_before`, `seq_after`;
- z wiersza `probe_summary`: `clipboard_updates` i `failed_opens`.

#### Próba przerwania blokady (nr 6)

Okno B, przy uruchomionej sondzie:

```powershell
.\CpbClipboardBlocker.exe --hold-ms 10000
```

Po pojawieniu się wiersza `hold_start` odczekaj około 3 s i naciśnij `Ctrl+C`
(wyraźnie przed upływem 10 s — odstępstwo od pierwotnej wartości 60000 ms,
przyjęte 18.11.2026). Następnie osobno:

```powershell
"EXIT=$LASTEXITCODE"
.\CpbSyntheticOwner.exe
```

Zapisz `EXIT` blokady (wartość po `Ctrl+C` może być niezerowa — zapisz ją bez
interpretacji), `EXIT` właściciela, `text_published` z jego wiersza `publish`
oraz wiersz zdarzenia w sondzie.

#### Blokada okresowa (nr 11)

Blokada działa w osobnym oknie i zapisuje własny dziennik metadanych (tylko
wiersze `hold_start`, `hold_end`, `hold open=failed` — bez treści schowka).
Okno B, przy uruchomionej sondzie:

```powershell
$bstamp = Get-Date -Format 'yyyyMMdd-HHmmss'
Start-Process -FilePath .\CpbClipboardBlocker.exe -WorkingDirectory $PWD.Path -ArgumentList '--hold-ms', '200', '--count', '25', '--pause-ms', '20', '--log', "..\wyniki\s07-blocker-$bstamp.log"
.\CpbSyntheticOwner.exe --count 10 --interval-ms 300 --vary
```

`--count 25` zamiast 100 to odstępstwo od pierwotnego protokołu, przyjęte
18.11.2026. Sondę zatrzymaj dopiero **po samoczynnym zamknięciu okna
blokady** (przy tych parametrach kilka sekund po zakończeniu właściciela).
Następnie sprawdź dziennik blokady:

```powershell
Select-String -Path "..\wyniki\s07-blocker-$bstamp.log" -Pattern 'type=hold ', 'type=blocker_stop'
```

Zapisz: `EXIT` właściciela, liczbę wierszy `publish` z `open=ok` i z
`open=failed`, liczbę wierszy `publish` z `text_published=true`, liczbę zdarzeń z `synthetic_fmt=present` w sondzie i liczbę
`open=failed` wśród nich, liczbę nieudanych otwarć blokady (`type=hold
... open=failed`) oraz to, czy jest wiersz `blocker_stop`.

#### Zakończenie każdej próby

1. Zatrzymaj sondę `Ctrl+C` i sprawdź zamknięcie dziennika (krok 6
   „Przebiegu każdej próby"): dokładnie jeden `probe_summary` i jeden
   `probe_stop`.
2. Sprawdź, czy żaden program testowy nie działa (lista procesów, bez
   dostępu do schowka):

   ```powershell
   Get-Process -Name CpbClipboardBlocker, CpbSyntheticOwner, CpbClipboardProbe -ErrorAction SilentlyContinue
   ```

   Polecenie nie powinno nic wypisać. Jeżeli działa jeszcze
   `CpbClipboardBlocker`, zakończ go `Stop-Process -Name CpbClipboardBlocker`,
   zapisz to w notatkach i uznaj próbę za nieważną.

#### Jak czytać wyniki

- **`EXIT=0` nie oznacza publikacji tekstu.** Właściciel ponawia otwarcie
  schowka do 400 razy co około 5 ms (realnie co najmniej 2 s, zwykle dłużej
  przez rozdzielczość zegara systemu). `EXIT=0` znaczy tylko, że każda
  transakcja **otworzyła schowek** w tym czasie. Czy tekst faktycznie
  opublikowano, pokazuje dopiero `text_published=true` w wierszu `publish`;
  `text_published=false` przy `open=ok` i `EXIT=0` oznacza, że otwarcie się
  udało, ale tekstu nie ustawiono.
- **Publikacja udana to nie to samo co natychmiastowa.** Wiersz `publish` z
  `open=ok` nie podaje liczby prób ani czasu otwarcia, więc obecne narzędzia
  **nie pozwalają stwierdzić**, że publikacja nastąpiła „od razu".
- **`EXIT=0` nie potwierdza blokady.** Właściciel ponownie otwiera schowek do
  blokady jedną próbą, bez ponawiania. Jeżeli wcześniej zdąży inny program
  (np. usługa historii `Win+V` albo sama sonda), wiersz `publish` pokaże
  `hold_after=failed`, a `EXIT` nadal wyniesie `0`.
- **Zdarzenie może zostać obsłużone dopiero po zwolnieniu schowka.** Sonda z
  ponawianiem czeka między próbami we własnym wątku; `open=ok` przy
  `open_attempts` większym niż 1 oznacza, że schowek zwolniono w trakcie
  oczekiwania. W blokadzie okresowej kolejne zdarzenia czekają w kolejce:
  `seq_before`, obecność formatów i `seq_after` opisują stan w chwili obsługi,
  nie w chwili zmiany, a `seq_before` wyższe niż `seq` właściciela oznacza
  obsługę spóźnioną.
- Przy `open=failed` pola `*_fmt` są nadal odczytane (bez otwierania
  schowka), a `history_val` i `cloud_val` mają zawsze wartość `-`.
- Sonda nie ponawia zdarzenia po czasie: po wyczerpaniu prób zapisuje
  `open=failed` i nie tworzy kolejnego wiersza, gdy blokada się skończy.
- `open_time` może wypaść w wyższym przedziale, niż wynika z liczby prób i
  przerwy, bo rzeczywisty czas uśpienia zależy od zegara systemu.

#### Cztery różne fakty — nie myl ich

| Fakt | Skąd | Co znaczy | Rola |
|---|---|---|---|
| Otwarcie schowka przez właściciela | `EXIT=0` (każdy wiersz `publish` ma `open=ok`) | każda transakcja otworzyła schowek w czasie ponawiania właściciela; nic nie mówi o publikacji tekstu, blokadzie ani czasie | warunek ważności prób 1–5 i 7–10; w próbach 6, 11 i 12 — wynik |
| Publikacja tekstu | `text_published=true` w wierszu `publish` | tekst testowy rzeczywiście ustawiono w schowku | warunek ważności prób 1–5 i 7–10; w próbach 6, 11 i 12 — wynik (w 11 i 12 liczba) |
| Ponowne otwarcie do blokady | `hold_after=ok` w wierszu `publish` | właściciel faktycznie zajął schowek na zadany czas po publikacji | warunek ważności prób z blokadą właściciela; bez niego próba nie mierzy blokady |
| Obserwacja rywalizacji w sondzie | dziennik sondy: `open`, `open_error`, `open_attempts`, `open_time`, `seq_before`/`seq_after` | to, co sonda faktycznie zobaczyła | **zawsze wynik, nigdy warunek ważności** |

Za wynik uznaje się każdy z wariantów obserwacji sondy, bez wyróżniania
żadnego z góry: `open=ok` przy pierwszej próbie (rywalizacji nie
zaobserwowano), `open=ok` po kilku próbach (zdarzenie obsłużone dopiero po
zwolnieniu schowka), `open=failed` po wyczerpaniu prób, a także obsługa
spóźniona (`seq_before` wyższe niż `seq` właściciela). Nieudane
`OpenClipboard` w sondzie **nie** jest warunkiem ważności żadnej próby.

#### Kryteria ważności próby

Próba jest **ważna**, gdy jednocześnie:

1. dziennik sondy jest zamknięty (`probe_summary` i `probe_stop`);
2. po próbie nie działa żaden program testowy;
3. kod `EXIT` każdego uruchomienia właściciela jest zapisany, a żaden nie
   wynosi `2` (`EXIT=2` oznacza błędne polecenie — nieudane wywołanie);
4. w próbach 1–5 i 7–10 każde uruchomienie właściciela ma `EXIT=0` **oraz**
   `text_published=true` w wierszu `publish`. `EXIT=3` (schowek nieotwarty)
   albo `text_published=false` (schowek otwarty, tekst nieustawiony) czyni
   próbę nieważną — zapisz wiersz `publish` i powtórz próbę. W próbie 6
   `EXIT` i `text_published` właściciela uruchomionego po przerwaniu blokady
   są **wynikiem** (czy po przerwaniu dało się otworzyć schowek i
   opublikować tekst); `EXIT=3` albo `text_published=false` oznacza
   zatrzymanie S7 przed próbą 7;
5. w próbach z blokadą właściciela (2–5 i 7–10) dodatkowo `hold_after=ok`;
   `hold_after=failed` czyni próbę nieważną jako pomiar blokady — zapisz
   wiersz `publish` i powtórz próbę;
6. w dzienniku sondy jest zdarzenie z `synthetic_fmt=present` dla każdej
   publikacji z `open=ok`; w próbach 11 i 12 opisz każdą różnicę liczby
   zdarzeń i publikacji, bez rozstrzygania przyczyny;
7. w czasie próby nie ma obcych zdarzeń (`clipboard_update` z
   `synthetic_fmt=absent`), poza próbami 11 i 12, w których trzeba je tylko
   policzyć;
8. w próbie 6 na ekranie blokady jest `hold_start`, a **nie ma** `hold_end`
   (przerwanie nastąpiło przed naturalnym końcem); w próbach 11 i 12 dziennik
   blokady zawiera `blocker_stop`.

Próba nieważna nie jest wynikiem negatywnym: zapisz przyczynę i powtórz ją z
nowym dziennikiem. W próbach 11 i 12 `EXIT=3` oraz wiersze `publish` z
`open=failed` lub `text_published=false` przy spełnionych pozostałych
kryteriach są wynikiem (liczbą publikacji udanych i nieudanych pod blokadą
okresową), a nie błędem próby.

**Podejrzenie błędu sondy** (opisz, nie interpretuj jako zachowania Windows):
`open=failed` z `open_error=0`; `open_attempts` większe niż ustawiony limit;
`history_val` lub `cloud_val` inne niż `-` przy `open=failed`; `failed_opens`
w `probe_summary` różne od liczby wierszy `open=failed`; `seq_after` mniejsze
niż `seq_before`; wiersze `probe_error`; brak `probe_summary` lub
`probe_stop` mimo zatrzymania `Ctrl+C`.

Wyniku Windows (czy i kiedy sonda otworzy schowek przy danym czasie blokady)
nie zakłada się z góry — zapisuje się to, co pokazały dzienniki.

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
