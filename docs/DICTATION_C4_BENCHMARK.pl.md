# CopyPasteBin 1.3 — C4: plan rzeczywistego benchmarku STT

Status: Vosk 0.3.45, Vosk `small-pl-0.22`, whisper.cpp 1.9.5, Whisper tiny,
adapter `whisper-cli` i techniczny korpus audio są przygotowane lokalnie.
Data aktualizacji: 2026-11-12.

## Metodologia

Każdy kandydat otrzymuje dokładnie ten sam plik mono 16-bit PCM WAV 16 kHz.
Każdy przypadek wykonuje się trzy razy, w stałej kolejności rotowanej między
silnikami. Pierwszy przebieg mierzy zimną inicjalizację, a kolejne dwa działają
po zwolnieniu poprzedniego procesu; model jest ładowany od nowa w każdym
przebiegu. Nie wolno wykonywać innych ciężkich zadań równolegle.

Są dwa osobne tory i dwa jawne sposoby podawania danych:

1. **Jakość końcowa:** Vosk i wszystkie modele Whisper przetwarzają cały ten
   sam plik. Mierzymy WER, CER, zgodność interpunkcji, CPU, RSS, czas
   inicjalizacji, czas końcowy, RTF i opóźnienie po końcu audio.
2. **Zachowanie na żywo:** wynik jest porównywany tylko w obrębie jawnej klasy
   `streaming` albo `windowed`. Vosk emituje częściowe wyniki podczas podawania
   kolejnych ramek PCM. `whisper-cli` jest testem `batch` i nie otrzymuje
   fikcyjnego czasu pierwszego wyniku. Ewentualny adapter ponownie analizujący
   rosnące okno audio jest oznaczany `windowed`, nie `streaming`.

`input_pacing=fast` podaje plik bez czekania i mierzy przepustowość, CPU, RAM,
inicjalizację oraz jakość. `input_pacing=realtime` udostępnia kolejne fragmenty
według terminów z zegara monotonicznego i dopiero wtedy pozwala interpretować
opóźnienie częściowe oraz końcowe jako symulację dyktowania. Raporty tych trybów
nie są łączone. `whisper-cli` pozostaje `batch/fast` i nie otrzymuje fikcyjnych
wyników częściowych.

Stabilność częściowych wyników to częstotliwość aktualizacji na sekundę i
średnia znormalizowana odległość edycyjna między kolejnymi podglądami. Brak
częściowych wyników pozostaje `null`, a nie zerem.

`run_isolated.py` jest jedyną wspieraną ścieżką uruchomienia: ustanawia profil
`bwrap`, a `run_adapter.py` przed startem silnika sprawdza montowania tylko do
odczytu, brak `/home`, `/etc/passwd` i `/dev/snd`, brak zewnętrznych interfejsów
i tras domyślnych oraz brak capabilities. Runner obserwuje ramki `ready`,
`partial`, `final`, `stopped`, utrzymuje sesję, kolejność i segmenty C1–C3,
mierzy zasoby i zapisuje plik `0600`. Benchmarkowe ramki częściowe i końcowe
dodają pozycję audio wyłącznie do obliczenia opóźnienia; nie zmienia to
produkcyjnego protokołu edytora. `analyze_runs.py` nie wypisuje transkrypcji.
Launcher akceptuje tylko pełne, dokładnie zgodne polecenia dwóch adapterów;
odrzuca testowe lub dowolne skrypty Pythona, dodatkowe flagi i nazwy modeli
niezgodne z kandydatem. Adapter działa w osobnej grupie procesów, którą runner
zabija w całości przy błędzie lub przekroczeniu limitu.

## Audio

`cases.json` nadal służy syntetycznym testom mechaniki adaptera. Pierwszy
rzeczywisty zestaw techniczny jest przypięty w `cases.tatoeba-pl.json` oraz
`audio-manifest.tatoeba-pl.json`: 20 krótkich wypowiedzi (łącznie 28,395 s)
jednego mówcy `antio`, opublikowanych przez Tatoeba i Wikimedia Commons.
Nagrania są CC BY 4.0, teksty referencyjne CC BY 2.0 FR. Manifest zachowuje
identyfikatory zdań, źródłowe URL-e, SHA-256 MP3 i wynikowych WAV, a także
oznacza transkodowanie GStreamerem do mono 16-bit PCM WAV 16 kHz. Jedna próbka
z serwerów Tatoeba i Wikimedia została porównana bajtowo. Zestaw wystarcza do
pierwszej kontroli działania i porównania technicznego, ale przez krótki czas,
jednego mówcę i brak liczb oraz terminologii technicznej nie jest dowodem
ogólnej jakości rozpoznawania.

Ewentualny późniejszy korpus jakości powinien zawierać 12–20 polskich klipów o
łącznym czasie około 2–4 minut: krótkie i długie wypowiedzi, liczby i daty,
nazwy własne, terminologię komputerową/AI, pauzy, autokorektę i urwane zdanie.
Nie należy rozszerzać obecnego zestawu o prywatne nagrania użytkowniczki.
Walidator odrzuca symlinki, wyjście poza katalog audio i inne formaty.

## Przypięte artefakty

| Element | Wersja/źródło | Pobranie | SHA-256 | Licencja |
| --- | --- | ---: | --- | --- |
| CMake, tylko lokalnie | PyPI 4.4.4 wheel x86_64 | 30 245 729 B | `f773a0544c66370408f451acd487c2c643b0dfebb48c5d64f3638bc1bb820238` | BSD-3-Clause / Apache-2.0 wrapper |
| libvosk | PyPI wheel 0.3.45, tag `cf2560c9f8a49d3d366b433fdabd78c518231bec` | 7 173 758 B | `25e025093c4399d7278f543568ed8cc5460ac3a4bf48c23673ace1e25d26619f` | Apache-2.0 |
| Vosk Polish | `vosk-model-small-pl-0.22` | około 50 MB | **brak oficjalnej sumy** | Apache-2.0 |
| whisper.cpp | tag v1.9.5, commit `d1be6fde11ac6e0407606b4e42fe72d34add8037` | Git, rozmiar do pomiaru | commit + zweryfikowany tag GitHub; brak opublikowanego SHA archiwum | MIT |
| Whisper tiny | HF commit `5359861c…`, `ggml-tiny.bin` | 77 691 713 B | `be07e048e1e599ad46341c8d2a135645097a538221678b7acdd1b1919c6e1b21` | MIT |
| Whisper base | ten sam commit, `ggml-base.bin` | 147 951 465 B | `60ed5bc3dd14eea856493d334349b405782ddcaf0028d4b5df4088345fba2efe` | MIT |
| Whisper small | ten sam commit, `ggml-small.bin` | 487 601 967 B | `1be3a9b2063867b937e64e2ec7483364a79917e157fa98c5d94b5c1fffea987b` | MIT |

Sumy Whisper pochodzą z oficjalnych metadanych LFS Hugging Face. Dla modelu
Vosk upstream publikuje nazwę, rozmiar przybliżony i licencję, ale nie
SHA-256. Suma obliczona po pierwszym pobraniu pozwoli powtórzyć nasze kolejne
testy, lecz nie będzie niezależnym dowodem autentyczności pierwszego pliku.

Aktualna maszyna ma x86_64, 8 logicznych CPU i około 16 GB RAM. Dostępne są
GCC/G++, `make`, `bwrap` i `unshare`; brakuje CMake, `ffmpeg`, `sox` i Ninja.
Nie są potrzebne FFmpeg ani SoX, jeśli korpus jest wcześniej przygotowany w
wymaganym WAV. CPU-only whisper.cpp wymaga lokalnego CMake, kompilatora i
`make`; Vosk użyje `libvosk.so` rozpakowanego z koła bez instalowania pakietu
Python.

## Bezpieczeństwo i najmniejsze uprawnienia

| Zysk | Nowa możliwość/ryzyko | Zabezpieczenie |
| --- | --- | --- |
| natywna inferencja | wykonanie pobranego kodu C/C++ | przypięte wersje, opublikowane SHA gdzie istnieje, przegląd źródła, osobny katalog |
| modele STT | duże nieprzejrzyste pliki | HTTPS, immutable commit HF, SHA-256 i limity rozmiaru; jawny brak SHA Vosk |
| pomiar offline | proces może próbować sieci | kontrolowany launcher ustanawia `bwrap --unshare-net`; runner weryfikuje profil przed startem silnika |
| pliki wynikowe | zawierają publiczne transkrypcje testowe | katalog testowy, tryb `0600`, brak stdout/logów z treścią |
| audio testowe | głos może być danymi osobowymi | tylko licencjonowany publiczny korpus lub świadomie wydany CC0; bez prywatnych klipów |

Proces dostaje tylko odczyt kodu, modelu i jednego klipu, prywatny katalog
wyników oraz pusty `/tmp`. Nie ma mikrofonu, urządzeń audio, schowka ani
historii CPB. Rozpoznawanie działa po zakończeniu pobierania bez sieci.

## Stan przygotowania i bezpieczne polecenia

Przenośny katalog eksperymentu:

```bash
C4_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}/copypastebin-stt-c4"
install -d -m 0700 "$C4_ROOT"/{downloads,tools,src,build,models,audio,results}
```

Artefakty są już przygotowane. Pełne źródła, rozmiary i sumy znajdują się w
`experiments/dictation-benchmark/artifacts.json`; nie należy pobierać ich
ponownie przed benchmarkiem.

Po zatwierdzeniu manifestu audio jedyną wspieraną ścieżką Vosk jest launcher.
Poniższy przykład symuluje tempo nagrywania; wariant wydajności plikowej wymaga
jednoczesnej zamiany `--input-pacing realtime` na `fast` oraz
`--feed-mode realtime` na `file`:

```bash
C4_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}/copypastebin-stt-c4"
python3 experiments/dictation-benchmark/run_isolated.py \
  --case-id pl-01 --engine vosk-small-pl-0.22 --run 1 \
  --mode streaming --input-pacing realtime --session c4-vosk-pl01-r1 \
  --audio "$C4_ROOT/audio/corpus-tatoeba-pl/pl-01.wav" \
  --engine-path "$C4_ROOT/tools/vosk/vosk/libvosk.so" \
  --model-path "$C4_ROOT/models/vosk-model-small-pl-0.22" \
  --results "$C4_ROOT/results/results.json" -- \
  /usr/bin/python3 /benchmark/adapters/vosk_ctypes.py \
  --library /engine --model /model --audio /audio/input.wav \
  --session c4-vosk-pl01-r1 --feed-mode realtime
```

Launcher sam tworzy osobne przestrzenie sieciową/PID/IPC/UTS, usuwa
capabilities, montuje wejścia tylko do odczytu i zapisuje wyłącznie do
prywatnego katalogu wyników oraz pustego `/tmp`. `run_adapter.py` odmawia pracy
poza tym profilem. Nie ma już flagi `--offline` do ręcznego potwierdzania.

Weryfikacja przygotowanego korpusu bez uruchamiania STT:

```bash
C4_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}/copypastebin-stt-c4"
python3 experiments/dictation-benchmark/validate_audio_manifest.py \
  --manifest experiments/dictation-benchmark/audio-manifest.tatoeba-pl.json \
  --cases experiments/dictation-benchmark/cases.tatoeba-pl.json \
  --audio-root "$C4_ROOT/audio"
```

Adapter Whisper jest uruchamiany przez ten sam launcher z trybem `batch/fast`
i dokładnym poleceniem adaptera zawierającym `--threads 4` oraz wewnętrzny
timeout krótszy o pięć sekund od limitu runnera. Bezpośrednie uruchomienie
`/engine/whisper-cli` nie spełnia protokołu i jest odrzucane.

Raport formatu 3:

```bash
C4_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}/copypastebin-stt-c4"
PYTHONDONTWRITEBYTECODE=1 python3 \
  experiments/dictation-benchmark/analyze_runs.py \
  --results "$C4_ROOT/results/results.json" \
  --cases experiments/dictation-benchmark/cases.tatoeba-pl.json
```

Odzyskiwalne usunięcie całego, osobnego środowiska C4 — wyłącznie po osobnej
decyzji o zakończeniu eksperymentu:

```bash
C4_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}/copypastebin-stt-c4"
gio trash -- "$C4_ROOT"
```

## Kolejność

1. Wykonano: dodać adapter `whisper-cli`, mały legalny korpus techniczny,
   teksty referencyjne i manifest z atrybucją oraz sumami.
2. Wykonano: pobrać lokalny CMake, libvosk, model Vosk i Whisper tiny;
   zweryfikować artefakty i przejrzeć rozpakowaną zawartość.
3. Po osobnej zgodzie uruchomić Vosk oraz Whisper tiny w torze jakości
   końcowej; Vosk dodatkowo w `streaming`.
4. Jeśli tiny mieści się w budżecie czasu, pobrać base, potem small.
5. Dopiero po wynikach zdecydować, czy warto budować adapter `windowed` dla
   Whisper. Nie podłączać mikrofonu ani edytora CPB w C4.

Źródła: oficjalne strony Vosk, PyPI, repozytorium whisper.cpp, API Hugging Face,
Tatoeba (teksty i pliki audio) oraz Wikimedia Commons (metadane licencji audio).
