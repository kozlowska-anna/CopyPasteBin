# Syntetyczny harness benchmarku dyktowania

Ten katalog przygotowuje porównywalne obliczanie WER, CER, opóźnień i użycia
zasobów. Nie uruchamia mikrofonu, silnika STT, modelu ani sieci i nie jest
częścią instalacji CopyPasteBin.

`cases.json` zawiera wyłącznie jawne, syntetyczne zdania po polsku. Zewnętrzny,
przyszły adapter silnika może zapisać wyniki trzech przebiegów do osobnego
pliku JSON w `/tmp`. Plik wyniku ma postać:

```json
{"version": 1, "results": [{
  "case_id": "pl-01", "engine": "vosk-small-pl-0.22", "run": 1,
  "transcript": "To jest syntetyczna próba lokalnego dyktowania.",
  "first_result_ms": 180, "final_result_ms": 740,
  "cpu_seconds": 0.52, "peak_rss_mib": 285, "model_bytes": 52428800
}]}
```

Dozwolone identyfikatory kandydatów są zamknięte: Vosk small PL 0.22 oraz
whisper.cpp tiny, base i small. Dokument odrzuca dodatkowe pola, duplikaty,
nieznane przypadki, niepoprawne liczby i zbyt długie transkrypcje.

```bash
python3 experiments/dictation-benchmark/score.py \
  --results /tmp/copypastebin-dictation-results.json
```

Raport stdout zawiera wyłącznie zagregowane metryki, bez transkrypcji i zdań
referencyjnych. Sam plik wejściowy może zawierać tylko transkrypcje podanych
syntetycznych zdań; nagrania nie są potrzebne ani zapisywane przez harness.

## Rzeczywiste przebiegi C4

`artifacts.json` przypina źródła, wersje, rozmiary i opublikowane sumy.
`adapters/vosk_ctypes.py` potrafi po zatwierdzonej instalacji zasilać protokół
C1–C3 z pliku PCM WAV, bez mikrofonu. Ma osobne tryby `file` i `realtime`;
drugi taktuje fragmenty zegarem monotonicznym. `run_isolated.py` ustanawia i
ogranicza profil `bwrap`, a `run_adapter.py` weryfikuje go przed startem
adaptera, mierzy czas ramek, CPU, RSS oraz rozmiar plików i dopisuje wynik
formatu 3 do prywatnego pliku `0600`. Bezpośrednie uruchomienie runnera albo
sama deklaracja `--offline` są odrzucane. `analyze_runs.py` rozdziela
`fast`/`realtime`, `streaming`/`windowed`/`batch`, WER, CER, interpunkcję,
inicjalizację, czas wyniku końcowego i zakończenia, opóźnienia względem pozycji
audio oraz stabilność wyników częściowych.

`adapters/whisper_cli.py` opakowuje przypięty `whisper-cli` wyłącznie jako
`batch/fast`. Przechwytuje i ogranicza JSON oraz diagnostykę, nie wypisuje
transkrypcji, emituje jedną ramkę końcową i oddziela czas ładowania modelu od
chwili zaobserwowania `ready`. Runner mierzy RSS całego drzewa adaptera, więc
obejmuje także potomny proces natywny.

Launcher porównuje całe polecenie adaptera z jedną z dwóch zatwierdzonych list,
łącznie z kolejnością i wartościami argumentów. Nie dopuszcza dowolnego skryptu
Pythona ani dodatkowych flag. Nazwy biblioteki/modelu muszą odpowiadać
przypiętemu kandydatowi. Timeout zabija całą osobną grupę procesów adaptera;
Whisper ma wewnętrzny limit krótszy o pięć sekund od limitu runnera.

`cases.tatoeba-pl.json` i `audio-manifest.tatoeba-pl.json` opisują techniczny
zestaw 20 krótkich polskich nagrań jednego mówcy Tatoeba. Audio `antio` jest
CC BY 4.0, teksty referencyjne CC BY 2.0 FR, a konwersję formatu jawnie
oznaczono w manifeście. Zestaw służy pierwszej kontroli adapterów, nie jest
reprezentatywnym dowodem jakości STT. `validate_audio_manifest.py` akceptuje
wyłącznie zwykłe, przypięte sumą SHA-256 pliki mono 16-bit PCM WAV 16 kHz
w jednym izolowanym katalogu.
Rozpoznawanie `batch`, okienkowe `windowed` i rzeczywiste `streaming` są
raportowane osobno. Kod nie pobiera artefaktów i nie uruchamia mikrofonu.

Kompletna metodologia i niewykonane polecenia instalacyjne znajdują się w
`docs/DICTATION_C4_BENCHMARK.pl.md` oraz wersji angielskiej `.en.md`.
