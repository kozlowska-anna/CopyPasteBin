# Etap 0 — protokół ręcznych testów na Windows 11

Cel: zebrać obserwacje o zachowaniu schowka Windows. Nie ma tu wyniku
„zaliczone/niezaliczone" dla systemu — każda obserwacja jest przydatna, także
nieoczekiwana. Jedyne twarde kryteria dotyczą samych narzędzi i są opisane w
sekcji „Kryteria dla narzędzi".

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

## Przygotowanie

```bat
cd windows
build.cmd
mkdir wyniki
```

Okno A — sonda. Okno B — pozostałe narzędzia. W każdym scenariuszu uruchom
sondę z nowym plikiem dziennika, wykonaj kroki w oknie B, zakończ sondę
`Ctrl+C`.

```bat
build\CpbClipboardProbe.exe --log wyniki\s01.log
```

## Scenariusze

### S0. Kompilacja i start

1. `build.cmd` — zapisz wszystkie ostrzeżenia i błędy kompilatora.
2. Uruchom sondę bez opcji i od razu zakończ `Ctrl+C`.

Zapisz: czy pojawiło się pytanie UAC (nie powinno), wartości `elevated`,
`listener_registration ok`, `session_registration ok`, czy na pasku zadań
pojawiło się jakiekolwiek okno sondy (nie powinno).

### S1. Jedna transakcja z kilkoma formatami

```bat
build\CpbSyntheticOwner.exe
```

Zapisz: ile wierszy `clipboard_update` powstało po jednym uruchomieniu oraz
wartości `seq_before` i `seq_after`.

### S2. Wielokrotna identyczna treść

```bat
build\CpbSyntheticOwner.exe --count 5 --interval-ms 500
```

Zapisz: liczbę zdarzeń i to, czy numer sekwencji rośnie przy identycznej
treści.

### S3. Szybka seria 100 zmian

```bat
build\CpbSyntheticOwner.exe --count 100 --vary
```

Zapisz: liczbę zdarzeń w sondzie (może być różna od 100), liczbę nieudanych
otwarć z wiersza `probe_summary`.

### S4. Opróżnienie i schowek bez tekstu

```bat
build\CpbSyntheticOwner.exe --empty-only
build\CpbSyntheticOwner.exe --no-text
```

Zapisz: czy opróżnienie daje zdarzenie i jaką wartość ma `text`.

### S5. Formaty prywatności — poprawne wartości

```bat
build\CpbSyntheticOwner.exe --exclude-monitor
build\CpbSyntheticOwner.exe --history 0
build\CpbSyntheticOwner.exe --history 1
build\CpbSyntheticOwner.exe --cloud 0
build\CpbSyntheticOwner.exe --cloud 1
build\CpbSyntheticOwner.exe --exclude-monitor --history 0 --cloud 0
```

Po każdym poleceniu naciśnij `Win+V` i zapisz, czy tekst testowy pojawił się w
historii Windows. Zapisz wartości `exclude_monitor`, `history_fmt`,
`history_val`, `cloud_fmt`, `cloud_val`, w tym ewentualny dopisek `_size_gt4`.

### S5c. Unikalny identyfikator a historia `Win+V`

Historia `Win+V` włączona. Sondę w oknie A uruchom z `--log` (katalog
`wyniki`). Właściciela w oknie B uruchamiaj **bez** `--log` — jego wyjście
(wiersz `canary_id`) celowo zawiera identyfikator i nie może trafić do
katalogu `wyniki`. Trzy próby, każda z innym automatycznym identyfikatorem:

```bat
build\CpbSyntheticOwner.exe --unique-canary --history 1 --cloud 0
build\CpbSyntheticOwner.exe --unique-canary --history 0 --cloud 0
build\CpbSyntheticOwner.exe --unique-canary --exclude-monitor --history 0 --cloud 0
```

Dla każdej próby odczytaj wiersz `canary_id` w oknie B, naciśnij `Win+V` i
zapisz, czy kafelek z **dokładnie** tym identyfikatorem się pojawił. Różne
identyfikatory pozwalają przypisać kafelek do konkretnej próby bez czyszczenia
historii między próbami.

Sprzątanie: usuń prawym przyciskiem tylko kafelki zaczynające się od
`CPB-STAGE0-CANARY-`.

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

```bat
build\CpbSyntheticOwner.exe --unique-canary --empty-only
build\CpbSyntheticOwner.exe --unique-canary --empty-only
build\CpbSyntheticOwner.exe --unique-canary --empty-only
```

Zapisz trzy wiersze `canary_id value=...`. Potwierdź: (a) każdy pasuje do
`^CPB-STAGE0-CANARY-[0-9A-F]{16}$`, (b) wszystkie trzy są różne. To ćwiczy
rzeczywisty `MakeCanaryId` (GUID → 16 znaków hex → wielkie litery), a nie analog.

### S6. Formaty prywatności — wartości uszkodzone

```bat
build\CpbSyntheticOwner.exe --history bad-value
build\CpbSyntheticOwner.exe --history short
build\CpbSyntheticOwner.exe --cloud bad-value
build\CpbSyntheticOwner.exe --cloud short
```

Zapisz: co raportuje sonda oraz czy Windows dodał wpis do `Win+V`.

Powtórz jedno polecenie z S5 przy sondzie uruchomionej z `--presence-only` i
potwierdź, że `history_val` oraz `cloud_val` mają wtedy wartość `-`.

### S7. Zajęty schowek

Blokada kontrolowana po publikacji — dla 50, 250, 1000 i 5000 ms:

```bat
build\CpbSyntheticOwner.exe --hold-after-ms 50
```

Najpierw z sondą bez opcji, potem z sondą uruchomioną tak:

```bat
build\CpbClipboardProbe.exe --open-attempts 10 --open-delay-ms 50 --log wyniki\s07b.log
```

Zapisz: `open`, `open_error`, `open_attempts`, `open_time` dla każdego czasu.

Blokada okresowa (inny program stale zajmuje schowek):

```bat
start build\CpbClipboardBlocker.exe --hold-ms 200 --count 100 --pause-ms 20
build\CpbSyntheticOwner.exe --count 10 --interval-ms 300 --vary
```

Zapisz: ile publikacji się powiodło i ile otwarć sondy się nie powiodło.

Zwolnienie po przerwaniu: uruchom
`build\CpbClipboardBlocker.exe --hold-ms 60000`, po kilku sekundach przerwij go
`Ctrl+C`, a następnie uruchom `build\CpbSyntheticOwner.exe`. Zapisz, czy
publikacja powiodła się od razu.

### S8. Opóźnione udostępnianie danych

Sonda z opcją `--render-synthetic` (prosi wyłącznie o format syntetyczny):

```bat
build\CpbClipboardProbe.exe --render-synthetic --log wyniki\s08.log
```

W oknie B kolejno, każde zakończ `Ctrl+C` po obejrzeniu wyniku:

```bat
build\CpbSyntheticOwner.exe --delay-synthetic-ms 0
build\CpbSyntheticOwner.exe --delay-synthetic-ms 1000
build\CpbSyntheticOwner.exe --delay-synthetic-ms 5000
build\CpbSyntheticOwner.exe --delay-synthetic-ms 120000
build\CpbSyntheticOwner.exe --delay-synthetic-ms 1000 --render-nothing
```

Przy wariancie 120000 (właściciel nie odpowiada) w trakcie oczekiwania skopiuj
w Notatniku dowolny tekst testowy, np. `abc`.

Zapisz: `synthetic_render` (wynik, kod błędu, przedział czasu), po jakim czasie
sonda odzyskała sterowność, czy zdarzenia z czasu blokady pojawiły się później
i w jakiej liczbie, jak zachowały się numery sekwencji.

Następnie przy sondzie **bez** `--render-synthetic`:

```bat
build\CpbSyntheticOwner.exe --delay-text-ms 2000 --stay-seconds 60
```

Zapisz: wartość `text` w sondzie oraz to, czy w oknie B pojawił się wiersz
`render_request format=text`, mimo że sonda o tekst nie prosi. Jeżeli tak,
tekstu zażądał inny składnik systemu (np. historia `Win+V`) — zanotuj, przy
jakich ustawieniach historii to wystąpiło.

### S9. Zdarzenia sesji i zasilania

Sonda musi zapisywać do pliku (`--log`). Dla każdego kroku osobny plik.

1. `Win+L`, odczekaj 10 s, odblokuj.
2. `Win+L`; przed zablokowaniem uruchom w oknie B
   `build\CpbSyntheticOwner.exe --count 20 --interval-ms 2000 --vary`, tak aby
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

1. Tekst kontrolny nie występuje w żadnym dzienniku **sondy**:

   ```bat
   findstr /s /c:"CPB-STAGE0-CANARY" wyniki\*.log
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
  wysłaniem);
- notatki z pól „Zapisz" dla każdego scenariusza;
- wersję Windows i ustawienia historii schowka;
- wszystko, co wyglądało na zawieszenie, błąd albo zaskoczenie.

Nie dołączaj zrzutów ekranu z historią `Win+V`, jeżeli widać na nich cokolwiek
poza tekstem testowym.

## Po testach

- Wyczyść historię schowka Windows.
- Usuń katalogi `windows\build` i `windows\wyniki`, jeśli nie są już potrzebne.
  Narzędzia nie zostawiają niczego poza nimi: nie zapisują ustawień, nie
  dodają autostartu i nie działają po zamknięciu okna.
