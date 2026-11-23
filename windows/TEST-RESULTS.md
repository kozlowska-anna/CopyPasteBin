# Etap 0 — wyniki testów na Windows

Podsumowania wykonanych scenariuszy z [TEST-PROTOCOL.md](TEST-PROTOCOL.md).
Każdy wpis rozdziela trzy rodzaje informacji:

- **Fakty z dziennika sondy** — to, co zapisała sonda (metadane, bez treści).
- **Obserwacje `Win+V`** — to, co osoba testująca zobaczyła w historii
  schowka; sonda historii `Win+V` nie sprawdza.
- **Ograniczenia dowodowe** — czego te dane nie dowodzą.

Dzienniki sondy, identyfikatory testowe i pliki `.exe` **nie są** częścią
repozytorium. Nazwy dzienników podano wyłącznie po to, by można było je
odnaleźć w lokalnym katalogu `windows\wyniki` komputera testowego.

## Środowisko

| Pozycja | Wartość |
|---|---|
| Komputer | Dell (komputer testowy) |
| System | Windows 11 Home, kompilacja 10.0.26200 |
| Architektura | x64 (AMD64) |
| Konto | zwykłe, `elevated=false` we wszystkich dziennikach |
| Historia `Win+V` | włączona |
| Synchronizacja między urządzeniami | *do uzupełnienia* |
| Sposób uruchamiania | interaktywny PowerShell, ręcznie |

---

## S5c — unikalny identyfikator a historia `Win+V` (18.11.2026)

**Ocena: zamknięty.**

### Fakty z dziennika sondy

| Dziennik | Próba | Format syntetyczny | `history_val` | `cloud_val` | `exclude_monitor` | Obce zdarzenia w czasie próby |
|---|---|---|---|---|---|---|
| `s05c-20261118-141020` | 1: `history=1 cloud=0` | obecny | 1 | 0 | absent | **tak** (przed próbą) |
| `s05c-20261118-141020` | 2: `history=0 cloud=0` | obecny | 0 | 0 | absent | **tak** (przed próbą) |
| `s05c-20261118-141020` | 3: `+exclude-monitor` | obecny | 0 | 0 | present | **tak** (przed próbą) |
| `s05c-r-20261118-142908` | — | — | — | — | — | podejście przerwane, brak publikacji |
| `s05c-r-20261118-143310` | 2 (powtórka) | obecny | 0 | 0 | absent | **nie** |
| `s05c-r-20261118-143310` | 3 (powtórka) | obecny | 0 | 0 | present | **nie** |

- Wartości flag mają poprawny rozmiar (brak dopisku `_size_gt4`).
- W pierwszym podejściu przed każdą próbą widać podwójne zdarzenie bez formatu
  syntetycznego, 2–3 s przed publikacją — ślad skopiowania polecenia do
  PowerShella. Pierwsze z tych zdarzeń dwukrotnie miało `open=failed
  open_error=5` (rywalizacja z programem kopiującym przy jednej próbie
  otwarcia).
- W powtórce S5c-R obce zdarzenia wystąpiły dopiero po próbie 3 (najpewniej
  kopiowanie wyników), poza oknem pomiaru.
- Wszystkie dzienniki zamknięte (`probe_summary`, `probe_stop`); w żadnym nie
  występuje `CPB-STAGE0-CANARY`.

### Obserwacje `Win+V`

| Próba | Obserwacja | Status |
|---|---|---|
| 1: `history=1 cloud=0` | identyfikator widoczny | kontrola pozytywna |
| 2: pierwsze podejście | zgłoszono „nowy identyfikator" | **unieważnione** — zanieczyszczenie kopiowanymi poleceniami, brak potwierdzenia zgodności znak po znaku |
| 3: pierwsze podejście | widoczny wpis z `exclude-monitor` | **unieważnione** — najpewniej kafelek ze skopiowanym poleceniem |
| 2: powtórka S5c-R | identyfikator **nieobecny** | wiążące |
| 3: powtórka S5c-R | identyfikator **nieobecny** | wiążące |
| `history=0 cloud=0` w S6 (15:14) | identyfikator **nieobecny**, `EXIT=0` | niezależne potwierdzenie próby 2 |

### Wniosek

Na tej kompilacji Windows wpis z `CanIncludeInClipboardHistory = 0` (DWORD)
nie trafia do historii `Win+V`; wpis z wartością `1` trafia. Pierwsze
podejście pokazało, że kopiowanie poleceń podczas pomiaru unieważnia
obserwacje — stąd „Zasady pomiaru" w protokole.

### Ograniczenia dowodowe

- Kody `EXIT` właściciela z powtórki S5c-R nie zostały zapisane; sonda
  potwierdza jednak, że obie publikacje się udały.
- Nie wyodrębniono wpływu samego `ExcludeClipboardContentFromMonitorProcessing`
  (próba 3 miała jednocześnie `history=0`).
- Każdy wariant w powtórce wykonano raz (próba 2 ma dodatkowe potwierdzenie w
  S6).
- Zmiany schowka między uruchomieniami sondy nie są rejestrowane.

---

## S6 — formaty prywatności z uszkodzonymi wartościami (18.11.2026)

**Ocena: PASS** (z ograniczeniami poniżej).

**Odstępstwo od pierwotnego protokołu:** według notatek osoby testującej
polecenia S6 wykonano z dodatkowym `--unique-canary`, aby kafelki `Win+V` dało
się przypisać do konkretnych prób. Dziennik sondy nie rejestruje tekstu
schowka, więc nie potwierdza tego niezależnie; ostatnia próba
(`--unique-canary --history 0 --cloud 0`) ma to potwierdzone wyjściem
właściciela.

### Fakty z dziennika sondy

| Dziennik | Wariant | Odczyt sondy | EXIT |
|---|---|---|---|
| `s06-20261118-144515` | `--history bad-value` | `history_fmt=present`, `history_val=invalid_value`, `cloud_fmt=absent` | nie zapisano |
| `s06-20261118-145651` | `--history short` | `history_fmt=present`, `history_val=invalid_short`, `cloud_fmt=absent` | nie zapisano |
| `s06b-20261118-150310` | `--cloud bad-value` | `cloud_fmt=present`, `cloud_val=invalid_value`, `history_fmt=absent` | nie zapisano |
| `s06-cloud-short-151109` | `--cloud short` | `cloud_fmt=present`, `cloud_val=invalid_short`, `history_fmt=absent` | 0 |
| `s06-presence-151408` (sonda `--presence-only`) | `--unique-canary --history 0 --cloud 0` | `presence_only=true`, `history_fmt=present`, `cloud_fmt=present`, `history_val=-`, `cloud_val=-` | 0 |

- We wszystkich próbach format syntetyczny obecny, `open=ok`, brak obcych
  zdarzeń w czasie próby.
- Ostatnia próba: `seq_after=2360` w dzienniku zgadza się z `seq=2360` w
  wierszu `publish` właściciela (`open=ok emptied=true text=set synthetic=set
  history=0:set cloud=0:set text_published=true`).
- Dzienniki bez publikacji testowej — **nieudane wywołania, nie wyniki**:
  `s06-20261118-144424` (dwa obce zdarzenia, najpewniej skopiowane polecenie),
  `s06-20261118-145143`, `s06-20261118-145313`, `s06b-20261118-150027`,
  `s06b-20261118-150146`, `s06-cloud-short-150946` (prawdopodobnie m.in.
  polecenia z błędną ścieżką `.\build\` uruchomione w katalogu
  `windows\build`; nieodnalezione polecenie nie uruchamia żadnego programu).
- Wszystkie 11 dzienników S6 zamknięte (`probe_summary`, `probe_stop`),
  `elevated=false`; w żadnym nie występuje `CPB-STAGE0-CANARY`.

### Obserwacje `Win+V`

| Wariant | Obserwacja |
|---|---|
| `--history bad-value` | nowy wpis widoczny |
| `--history short` | nowy wpis widoczny (program uruchomiony dwukrotnie) |
| `--cloud bad-value` | nowy wpis widoczny |
| `--cloud short` | nowy wpis widoczny |
| `--history 0 --cloud 0` (kontrola) | identyfikator nieobecny |

### Wniosek

Sonda poprawnie rozróżnia wartość nieprawidłową (`invalid_value`) i za krótką
(`invalid_short`) i nie wypisuje ich treści; w trybie `--presence-only` nie
odczytuje wartości flag. W obu testowanych wariantach uszkodzona lub za krótka
wartość `CanIncludeInClipboardHistory` **nie** ukryła wpisu przed `Win+V`;
spośród przetestowanych wariantów wpis był ukryty tylko przy poprawnym DWORD
`0` (S5c-R i próba kontrolna S6).

### Ograniczenia dowodowe

- Drugie uruchomienie `--history short` nie zostało zarejestrowane w żadnym
  dzienniku.
- Numer sekwencji schowka zmieniał się także między uruchomieniami sondy
  (np. 2083→2092, 2103→2131, 2138→2173, 2224→2268, 2303→2352); tych zmian nie
  da się przypisać.
- Kody `EXIT` zapisano tylko dla `--cloud short` i próby kontrolnej.
- Każdy wariant zarejestrowano raz.
- Warianty `--cloud` nie zawierały formatu historii, więc widoczność wpisu w
  `Win+V` jest dla nich oczekiwana i nie mówi nic o obsłudze
  `CanUploadToCloudClipboard` przez Windows; synchronizacji w chmurze nie
  sprawdzano.

---

## S7 — zajęty schowek (22–23.11.2026)

**Ocena: PASS** (z odstępstwami i ograniczeniami poniżej).

Sonda „zwykła" — domyślna, jedna próba otwarcia (dziennik `s07-`); sonda „z
ponawianiem" — `--open-attempts 10 --open-delay-ms 50` (dziennik `s07b-`).
Wszystkie dzienniki zamknięte (`probe_summary`, `probe_stop`), `elevated=false`;
po każdej próbie żaden program testowy nie działał; w żadnym dzienniku nie
występuje `CPB-STAGE0-CANARY`.

**Odstępstwa od protokołu:**

- Próba 6 (przerwanie blokady): blokadę przerwano poleceniem
  `Stop-Process -Name CpbClipboardBlocker` z trzeciego okna zamiast `Ctrl+C`
  — patrz „Ograniczenia dowodowe".
- Wykonano dwie dodatkowe, nieplanowane próby z blokadą właściciela 10 000 ms
  (pomyłka w poleceniu); jeden z tych dzienników ma mylącą nazwę (tabela).
- Właściciela uruchamiano zwykle bez dopisku `; "EXIT=$LASTEXITCODE"`.
- Próbę 12 (blokada okresowa ze 100 cyklami) pominięto, bo wynik próby 11
  jest jednoznaczny.

### Fakty z dzienników

Blokada właściciela (`--hold-after-ms`). We wszystkich próbach wiersz
`publish` właściciela: `open=ok`, `text_published=true`, `hold_after=ok`
(poza próbą 1, która nie ma blokady), a `seq` zgadza się z `seq_before`
zdarzenia sondy. Każda próba ma dokładnie jedno zdarzenie z
`synthetic_fmt=present` na jedną publikację i żadnego obcego zdarzenia.

| Nr | Dziennik | Blokada | Sonda | `open` | `open_error` | `open_attempts` | `open_time` | EXIT |
|---|---|---|---|---|---|---|---|---|
| 1 | `s07-k0-20261123-001811` | brak (3 publikacje) | zwykła | ok (3×) | 0 | 1 | lt1ms | 0 (odczytany po 3. uruchomieniu) |
| 2 | `s07-h50-20261123-002913` | 50 ms | zwykła | failed | 5 | 1 | lt1ms | wywnioskowany: 0 |
| 2 (powt.) | `s07-h50-20261123-003630` | 50 ms | zwykła | failed | 5 | 1 | lt1ms | wywnioskowany: 0 |
| 3 | `s07b-h50-20261123-004437` | 50 ms | z ponawianiem | ok | 0 | 2 | 50to250ms | wywnioskowany: 0 |
| 4 | `s07-h250-20261123-004437` | 250 ms | zwykła | failed | 5 | 1 | lt1ms | wywnioskowany: 0 |
| 5 | `s07b-h250-20261123-004854` | 250 ms | z ponawianiem | ok | 0 | 6 | 250msto1s | wywnioskowany: 0 |
| 7 | `s07-h1000-20261123-010705` | 1000 ms | zwykła | failed | 5 | 1 | lt1ms | wywnioskowany: 0 |
| 8 | `s07b-h1000-20261123-013404` | 1000 ms | z ponawianiem | failed | 5 | 10 | 250msto1s | wywnioskowany: 0 |
| 9 | `s07-h5000-20261123-013530` | 5000 ms | zwykła | failed | 5 | 1 | lt1ms | wywnioskowany: 0 |
| 10 | `s07b-h5000-20261123-013629` | 5000 ms | z ponawianiem | failed | 5 | 10 | 250msto1s | wywnioskowany: 0 |
| dod. | `s07-int-20261123-005030` | 10 000 ms | zwykła | failed | 5 | 1 | lt1ms | 0 |
| dod. | `s07-h1000-20261123-010542` (**nazwa myląca** — faktycznie 10 000 ms) | 10 000 ms | zwykła | failed | 5 | 1 | lt1ms | wywnioskowany: 0 |

„Wywnioskowany: 0" — kod nie został wypisany; właściciel zwraca `3` wyłącznie
przy publikacji z `open=failed` (`SyntheticOwner.cs`), a wszystkie te
publikacje mają `open=ok`.

Przerwanie blokady (próba 6):

| Dziennik | Przebieg w oknie blokady | EXIT blokady | Właściciel po blokadzie | Sonda |
|---|---|---|---|---|
| `s07-int-20261123-005255` | `hold_start`, `hold_end` po 10 s — **nie przerwano** | 0 | `open=ok`, `text_published=true` | `open=ok`, 1 próba |
| `s07-int-20261123-005633` | jak wyżej — **nie przerwano** | 0 | `open=ok`, `text_published=true` | `open=ok`, 1 próba |
| `s07-int-20261123-010058` | `hold_start`, brak `hold_end` i `blocker_stop` — przerwano przez `Stop-Process` | −1 | `open=ok`, `text_published=true`, `seq=563` | `open=ok`, 1 próba, `seq_before=563` |

Wiążący jest trzeci wiersz; dwa pierwsze dokumentują zwolnienie schowka po
naturalnym końcu blokady.

Blokada okresowa (próba 11): dzienniki `s07-per25-20261123-013859` (sonda
zwykła) i `s07-blocker-20261123-013900` (blokada).

- Blokada: 25 z 25 cykli `hold_start`/`hold_end` (po około 200 ms, przerwy
  około 30 ms), żadnego `hold open=failed`, wiersz `blocker_stop`.
- Właściciel (`--count 10 --interval-ms 300 --vary`): 10 z 10 publikacji z
  `open=ok` i `text_published=true`, `EXIT=0`; kolejne publikacje co około
  470 ms zamiast co 300 ms.
- Sonda: 10 zdarzeń z `synthetic_fmt=present`, `seq_before` zgodne z 10
  wartościami `seq` właściciela (774–828), wszystkie `open=ok` przy 1 próbie,
  `failed_opens=0`, brak obcych zdarzeń.

Nieudane wywołania (dzienniki bez publikacji testowej, nie są wynikami):
`s07-k0-20261122-233943`, `s07-k0-20261122-233953`, `s07-k0-20261122-234330`,
`s07-k0-20261122-234411`, `s07b-h50-20261123-003253`,
`s07b-h50-20261123-004249` (sonda działała, właściciela nie uruchomiono) oraz
`s07b-h50-20261123-003256` (sonda omyłkowo uruchomiona w oknie właściciela;
jedno obce zdarzenie, najpewniej kopiowanie wyników).

Obserwacja uboczna: wiersz `render_all_request` pojawia się przy każdym
zakończeniu właściciela, także bez opóźnionego renderowania.

### Wniosek

Gdy schowek jest zajęty, sonda dostaje `open=failed` z kodem `5` (odmowa
dostępu). Krótkie ponawianie (do 10 × 50 ms) pozwoliło otworzyć schowek przy
blokadzie 50 i 250 ms; przy blokadzie 1000 ms i dłuższej nie wystarczyło.
Liczba prób rosła z długością blokady (2 przy 50 ms, 6 przy 250 ms). Sonda
nie zgubiła żadnego zdarzenia — w każdej próbie jedno zdarzenie na jedną
publikację — i nie ponawiała zdarzenia po czasie. Po zabiciu programu, który
trzymał schowek, Windows od razu go zwolnił. Przy blokadzie okresowej (około
87% czasu zajętości) sonda z jedną próbą otwarcia ani razu nie trafiła na
blokadę, choć właściciel był przez nią spowalniany.

### Ograniczenia dowodowe

- `Ctrl+C` w dwóch podejściach nie przerwało blokady (blokada doszła do
  `hold_end`). Nie ustalono, czy klawisze nie trafiły do okna, czy zostały
  naciśnięte za późno, czy program nie reaguje; zwolnienie po `Ctrl+C` **nie**
  zostało więc potwierdzone — potwierdzone jest tylko zwolnienie po
  `Stop-Process`.
- Wyjaśnienie wyniku blokady okresowej (powiadomienie dociera do sondy, zanim
  blokada odzyska schowek) jest hipotezą; wynik dotyczy tych parametrów
  blokady i jednej serii.
- Kody `EXIT` w większości prób są wywnioskowane z kodu, nie odczytane.
- Wiersz `publish` z `open=ok` nie podaje liczby prób ani czasu otwarcia,
  więc nie wiadomo, jak długo właściciel czekał na schowek w próbie 11.
- Każdy wariant wykonano raz (50 ms z sondą zwykłą i 10 000 ms — dwa razy).
- Przedziały `open_time` są zgrubne; liczba prób w sondzie z ponawianiem
  zależy także od rozdzielczości zegara systemu.
- Zmiany schowka między uruchomieniami sondy (widoczne jako skoki numeru
  sekwencji, np. 313→357, 742→768) nie są rejestrowane ani przypisane.
