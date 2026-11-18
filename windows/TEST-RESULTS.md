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
