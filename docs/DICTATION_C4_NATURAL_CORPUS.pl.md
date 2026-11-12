# CopyPasteBin 1.3 — C4: plan korpusu naturalnej polskiej mowy

Status: **plan zatwierdzenia źródeł; żadnego nowego audio nie pobrano**.
Data przeglądu źródeł: 2026-11-12.

Dotychczasowy korpus Tatoeba, jego manifest i wyniki pozostają niezmienione.
Nowy etap ma sprawdzić dłuższą mowę wielu osób, a nie wyłonić zwycięzcę STT.

## Ocena źródeł

| Źródło | Licencja i autorstwo | Przydatność | Decyzja |
| --- | --- | --- | --- |
| VoxPopuli, polski ASR | Dane audio i transkrypcje: CC0; źródłowe nagrania Parlamentu Europejskiego. Repozytorium rozdziela licencję danych CC0 od licencji kodu i modeli CC BY-NC. Zalecane cytowanie Wang et al., ACL-IJCNLP 2021. | 111 godzin i 282 mówców; naturalne wypowiedzi parlamentarne; pola `audio_id`, `raw_text`, `speaker_id`, `is_gold_transcript`. Pełny polski eksport HF ma ok. 20,6 GB, ale Dataset Viewer pozwala pobierać pojedyncze wiersze i tymczasowe zasoby audio bez całego Parquet. | **Źródło podstawowe**, wyłącznie selektywny podzbiór z `test`, rewizja `5ab868a7cddb87d84224ebfc8112ebd0905fc5bd`. |
| Common Voice Scripted Speech 27.0 PL | CC0; zakaz prób ustalania tożsamości mówców i ponownego hostowania zbioru. | 4,49 GB w jednym oficjalnym archiwum; głównie krótkie wypowiedzi czytane. | Odłożone: pobranie całości narusza zasadę minimalizacji dla 15 próbek. |
| FLEURS `pl_pl` | CC BY 4.0; atrybucja korpusu FLEURS/Google i publikacji. | Selektywny dostęp jest możliwy, lecz schemat publiczny nie zawiera identyfikatora mówcy, a domeną jest mowa czytana. Polski config ma ok. 2,05 GB. | Rezerwa, **nie jest liczona** do minimum różnych mówców. |

Źródła informacji:

- <https://github.com/facebookresearch/voxpopuli>
- <https://huggingface.co/datasets/facebook/voxpopuli>
- <https://huggingface.co/docs/dataset-viewer/rows>
- <https://mozilladatacollective.com/datasets/cmu5wsxwp00e0nq07m8v0274j>
- <https://commonvoice.mozilla.org/dav/terms>
- <https://huggingface.co/datasets/google/fleurs>

## Docelowy podzbiór

Plan obejmuje 15 klipów: pięciu pseudonimowych `speaker_id`, po trzy klipy na
mówcę. Każdy klip ma trwać 10–30 sekund, a suma 3–6 minut. Limit ruchu dla
audio i niezbędnych metadanych wynosi 25 MB. Osiągnięcie limitu przed uzyskaniem
pięciu mówców albo 180 sekund oznacza przerwanie, nie pobranie pełnego zbioru.

Po osobnej zgodzie procedura będzie następująca:

1. potwierdzić rewizję, licencję danych i dostępność splitu `test`;
2. odczytać metadane małymi stronami, bez audio, i zachować tylko rekordy
   `is_gold_transcript`, z `raw_text` oraz pseudonimowym `speaker_id`;
3. nie wyszukiwać ani nie ustalać prawdziwej tożsamości mówców;
4. pobrać wyłącznie kandydatów, zatrzymując się przy 25 MB;
5. odrzucić klipy poza 10–30 s i wybrać pięć identyfikatorów mówców
   leksykograficznie, po trzy najniższe stabilne `audio_id` spełniające sloty;
6. zapisać hash źródła, następnie przekonwertować istniejącym GStreamerem do
   mono PCM WAV 16 kHz i zapisać drugi hash;
7. skopiować tekst referencyjny z przypiętych metadanych; nigdy z wyniku STT.

Plan slotów znajduje się w
`audio-manifest.natural-pl.plan.json`, a oddzielny, celowo nieuruchamialny plan
referencji w `cases.natural-pl.plan.json`. Po pobraniu powstaną osobne pliki
`audio-manifest.natural-pl.json` w wersji 3 i `cases.natural-pl.json` w wersji
1. Audio i transkrypcje wynikowe nie trafią do Git.

## Pokrycie i ograniczenia

VoxPopuli dobrze pokrywa dłuższą naturalną wypowiedź, liczby i daty, nazwy
własne, pauzy, zmianę tempa oraz zdania przydatne do oceny interpunkcji.
Korpus parlamentarny nie jest rozmową codzienną. Nie gwarantuje terminologii
Linux/GitHub/Python/AI ani naturalnych autokorekt. Te trzy kategorie są jawnie
oznaczone jako planowane braki; nie dobieramy sztucznie lub ręcznie tekstów po
wynikach silników. Pięciu mówców z jednej domeny nadal nie reprezentuje całej
polskiej mowy, akcentów, warunków akustycznych ani dyktowania przy komputerze.

## Metryki jakości v2

Historyczne `wer`, `cer` i `mean_punctuation_accuracy` pozostają w raporcie,
aby nie zmieniać wcześniejszych wyników. Analyzer raportuje teraz wersję 4 i
dodaje jawnie opisane pola:

- `normalized_wer`: NFC, `casefold`, tokeny słowne Unicode, pojedyncze spacje;
- `normalized_cer`: CER tego samego tekstu znormalizowanego, bez interpunkcji;
- `punctuation_aware_cer`: NFC, `casefold`, złożone białe znaki, interpunkcja
  zachowana;
- ocenę znaków interpunkcyjnych na granicach słów: poprawne, brakujące,
  nadmiarowe i przesunięte;
- precision/recall/F1 interpunkcji tylko tam, gdzie znormalizowane słowa są
  identyczne. Błędy słowne blokujące wiarygodną ocenę położenia znaku są
  liczone osobno.

Stara miara porównywała wyłącznie kolejność znaków, ignorując ich pozycję.
Mogła więc uznać przecinek przesunięty do innej granicy słowa za poprawny.
Nowa metoda nie miesza tego błędu z brakiem interpunkcji i nie udaje, że można
jednoznacznie ocenić pozycję znaku przy różnych słowach.

Ponowna, tylko odczytowa analiza zachowanego wyniku Tatoeba pokazuje wpływ
definicji. Dla Vosk CER bez interpunkcji wynosi 6,383%, a CER z interpunkcją
10,9312%; w 11 leksykalnie bezbłędnych klipach nie było kompletnej poprawnej
interpunkcji. Dla Whisper wartości wynoszą odpowiednio 16,383% i 16,3968%; z
20 klipów tylko 6 miało słowa wystarczająco zgodne do niezależnej oceny
położenia znaków i wszystkie 6 miało poprawną interpunkcję. Historyczne 80%
Whispera oznaczało zgodność samej sekwencji znaków w 16/20 klipów, także tam,
gdzie błędy słowne uniemożliwiały wiarygodną ocenę położenia. Nie należy więc
interpretować 0% kontra 80% jako samodzielnego testu jakości interpunkcji.

## Plan przyszłego benchmarku

Po zatwierdzeniu i walidacji korpusu:

- oba silniki dostaną dokładnie te same WAV;
- Vosk: `streaming/fast`, trzy powtórzenia wydajności;
- Whisper tiny: `batch/fast`, `--language pl`, trzy powtórzenia;
- jakość będzie wnioskowana z 15 unikalnych wypowiedzi, nie z 45 uruchomień;
- raport obejmie obie pary WER/CER, interpunkcję v2, bezbłędne wypowiedzi,
  CPU, RSS, `completed_ms` i rozrzut powtórzeń;
- wybrane dłuższe klipy Vosk przejdą osobno przez `realtime`; batch Whispera
  nie będzie przedstawiany jako odpowiednik streamingu.

## Bezpieczeństwo i bramka zgody

Nie pobrano audio, nie zainstalowano narzędzi i nie uruchomiono inferencji.
Przyszłe pliki pozostaną w prywatnym katalogu C4 (`0700`, pliki `0600`).
`validate_natural_audio_manifest.py` wymusza liczbę próbek, co najmniej trzech
mówców, dozwolone licencje, przypięte rewizje, SHA-256, format WAV, czas,
kategorie, katalog `0700`, pliki `0600` i zgodność jeden-do-jednego z
referencjami.

Osobnej zgody wymagają: pierwszy dostęp sieciowy do wybranych rekordów,
pobranie maksymalnie 25 MB audio, konwersja i późniejsza inferencja. Jeśli
Dataset Viewer nie pozwoli pobrać pojedynczych rekordów, zadanie zatrzymuje się;
nie pobieramy archiwum 20,6 GB ani 4,49 GB jako obejścia.
