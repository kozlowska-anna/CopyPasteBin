# CopyPasteBin 1.3 — C4: plan rzeczywistego benchmarku STT

Status: środowisko pomiarowe przygotowane; brak pobranych silników, modeli i
audio. Data: 2026-11-11.

## Metodologia

Każdy kandydat otrzymuje dokładnie ten sam plik mono 16-bit PCM WAV 16 kHz.
Każdy przypadek wykonuje się trzy razy, w stałej kolejności rotowanej między
silnikami. Pierwszy przebieg mierzy zimną inicjalizację, a kolejne dwa działają
po zwolnieniu poprzedniego procesu; model jest ładowany od nowa w każdym
przebiegu. Nie wolno wykonywać innych ciężkich zadań równolegle.

Są dwa osobne tory:

1. **Jakość końcowa:** Vosk i wszystkie modele Whisper przetwarzają cały ten
   sam plik. Mierzymy WER, CER, zgodność interpunkcji, CPU, RSS, czas
   inicjalizacji, czas końcowy, RTF i opóźnienie po końcu audio.
2. **Zachowanie na żywo:** wynik jest porównywany tylko w obrębie jawnej klasy
   `streaming` albo `windowed`. Vosk emituje częściowe wyniki podczas podawania
   kolejnych ramek PCM. `whisper-cli` jest testem `batch` i nie otrzymuje
   fikcyjnego czasu pierwszego wyniku. Ewentualny adapter ponownie analizujący
   rosnące okno audio jest oznaczany `windowed`, nie `streaming`.

Stabilność częściowych wyników to częstotliwość aktualizacji na sekundę i
średnia znormalizowana odległość edycyjna między kolejnymi podglądami. Brak
częściowych wyników pozostaje `null`, a nie zerem.

`run_adapter.py` obserwuje ramki `ready`, `partial`, `final`, `stopped`,
utrzymuje sesję, kolejność i segmenty C1–C3, mierzy zasoby i zapisuje plik
`0600`. `analyze_runs.py` nie wypisuje transkrypcji. Adapter nie zmienia
protokołu edytora; tłumaczy API silnika na istniejące ramki.

## Audio

Obecne `cases.json` służy testom technicznym adaptera, nie jest dowodem jakości
STT. Docelowy mały korpus jakości powinien zawierać 12–20 polskich klipów o
łącznym czasie około 2–4 minut: krótkie i długie wypowiedzi, liczby i daty,
nazwy własne, terminologię komputerową/AI, pauzy, autokorektę i urwane zdanie.

Preferowanym źródłem jest deterministycznie wybrany podzbiór polskiego Mozilla
Common Voice, ponieważ wersja 27.0 jest oznaczona CC0-1.0. Pełny zbiór ma około
4,49 GB i jego pobranie byłoby nieproporcjonalne; najpierw trzeba ustalić, czy
Mozilla Data Collective pozwoli pobrać mały podzbiór bez pełnego archiwum.
Nie pobrano żadnego klipu. Alternatywą jest nowy zestaw nagrany specjalnie i
świadomie udostępniony jako CC0 przez osobę testującą — nie prywatne nagranie
użytkowniczki.

Każdy zatwierdzony klip otrzyma wpis manifestu: identyfikator, dokładny tekst,
źródłowy URL/ID, licencję, cel `technical`/`quality` i SHA-256. Walidator
odrzuca symlinki, wyjście poza katalog audio i inne formaty.

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
| pomiar offline | proces może próbować sieci | osobna przestrzeń sieciowa `bwrap --unshare-net`; `offline=true` tylko dla takiego przebiegu |
| pliki wynikowe | zawierają publiczne transkrypcje testowe | katalog testowy, tryb `0600`, brak stdout/logów z treścią |
| audio testowe | głos może być danymi osobowymi | tylko licencjonowany publiczny korpus lub świadomie wydany CC0; bez prywatnych klipów |

Proces dostaje tylko odczyt kodu, modelu i jednego klipu, prywatny katalog
wyników oraz pusty `/tmp`. Nie ma mikrofonu, urządzeń audio, schowka ani
historii CPB. Rozpoznawanie działa po zakończeniu pobierania bez sieci.

## Polecenia do oceny — niewykonane

Katalog eksperymentu:

```bash
install -d -m 0700 /home/anna/.local/share/copypastebin-stt-c4/{downloads,tools,src,build,models,audio,results}
```

Każdy artefakt należy pobierać osobnym `curl --proto '=https' --tlsv1.2
--fail --location`, do `downloads/`, następnie sprawdzić dokładną sumą z tabeli
przed rozpakowaniem. Pełne URL-e i sumy są maszynowo zapisane w
`experiments/dictation-benchmark/artifacts.json`.

Przykład CMake i Vosk po weryfikacji:

```bash
python3 -m zipfile -e /home/anna/.local/share/copypastebin-stt-c4/downloads/cmake-4.4.4.whl /home/anna/.local/share/copypastebin-stt-c4/tools/cmake
python3 -m zipfile -e /home/anna/.local/share/copypastebin-stt-c4/downloads/vosk-0.3.45.whl /home/anna/.local/share/copypastebin-stt-c4/tools/vosk
```

Przypięcie whisper.cpp:

```bash
git clone --filter=blob:none --no-checkout https://github.com/ggml-org/whisper.cpp.git /home/anna/.local/share/copypastebin-stt-c4/src/whisper.cpp
git -C /home/anna/.local/share/copypastebin-stt-c4/src/whisper.cpp checkout --detach d1be6fde11ac6e0407606b4e42fe72d34add8037
/home/anna/.local/share/copypastebin-stt-c4/tools/cmake/cmake/data/bin/cmake -S /home/anna/.local/share/copypastebin-stt-c4/src/whisper.cpp -B /home/anna/.local/share/copypastebin-stt-c4/build/whisper.cpp -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON -DWHISPER_BUILD_TESTS=OFF
/home/anna/.local/share/copypastebin-stt-c4/tools/cmake/cmake/data/bin/cmake --build /home/anna/.local/share/copypastebin-stt-c4/build/whisper.cpp --target whisper-cli -j 8
```

Przykładowy Vosk po zatwierdzeniu modelu i manifestu audio:

```bash
bwrap --unshare-net --die-with-parent --ro-bind / / --bind /home/anna/.local/share/copypastebin-stt-c4/results /home/anna/.local/share/copypastebin-stt-c4/results --tmpfs /tmp --dev /dev --proc /proc python3 experiments/dictation-benchmark/run_adapter.py --case-id pl-01 --engine vosk-small-pl-0.22 --run 1 --mode streaming --session c4-vosk-pl01-r1 --audio /home/anna/.local/share/copypastebin-stt-c4/audio/pl-01.wav --engine-path /home/anna/.local/share/copypastebin-stt-c4/tools/vosk/vosk/libvosk.so --model-path /home/anna/.local/share/copypastebin-stt-c4/models/vosk-model-small-pl-0.22 --results /home/anna/.local/share/copypastebin-stt-c4/results/results.json --offline -- python3 experiments/dictation-benchmark/adapters/vosk_ctypes.py --library /home/anna/.local/share/copypastebin-stt-c4/tools/vosk/vosk/libvosk.so --model /home/anna/.local/share/copypastebin-stt-c4/models/vosk-model-small-pl-0.22 --audio /home/anna/.local/share/copypastebin-stt-c4/audio/pl-01.wav --session c4-vosk-pl01-r1
```

Ta pierwsza wersja `bwrap` odcina sieć, ale ma szeroki odczyt `/`; przed
rzeczywistym uruchomieniem należy zawęzić bindy do bibliotek systemowych,
repozytorium i katalogu eksperymentu. Nie należy przedstawiać samej flagi
`--offline` jako dowodu izolacji.

Raport:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 experiments/dictation-benchmark/analyze_runs.py --results /home/anna/.local/share/copypastebin-stt-c4/results/results.json
```

Usunięcie jest odzyskiwalne i nie dotyka instalacji CPB:

```bash
gio trash /home/anna/.local/share/copypastebin-stt-c4
```

## Kolejność

1. Zatwierdzić źródło małego korpusu audio i utworzyć jego manifest.
2. Pobrać lokalny CMake, libvosk, model Vosk i Whisper tiny; zweryfikować
   artefakty i przejrzeć rozpakowaną zawartość.
3. Uruchomić Vosk oraz Whisper tiny w torze jakości końcowej; Vosk dodatkowo w
   `streaming`.
4. Jeśli tiny mieści się w budżecie czasu, pobrać base, potem small.
5. Dopiero po wynikach zdecydować, czy warto budować adapter `windowed` dla
   Whisper. Nie podłączać mikrofonu ani edytora CPB w C4.

Źródła: oficjalne strony Vosk, PyPI, repozytorium whisper.cpp, API Hugging Face
oraz warunki i katalog Mozilla Common Voice.
