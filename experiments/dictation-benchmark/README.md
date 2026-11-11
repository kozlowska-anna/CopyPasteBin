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
