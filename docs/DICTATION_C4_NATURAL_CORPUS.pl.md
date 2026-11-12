# CopyPasteBin 1.3 — C4: plan korpusu naturalnej polskiej mowy

Status: **zatrzymane przed audio: brak bezpiecznego selektywnego dostępu**.
Data przeglądu źródeł: 2026-11-12.

Dotychczasowy korpus Tatoeba, jego manifest i wyniki pozostają niezmienione.
Nowy etap ma sprawdzić dłuższą mowę wielu osób, a nie wyłonić zwycięzcę STT.

## Ocena źródeł

| Źródło | Licencja i autorstwo | Przydatność | Decyzja |
| --- | --- | --- | --- |
| VoxPopuli, polski ASR | Dane audio i transkrypcje: CC0; źródłowe nagrania Parlamentu Europejskiego. Repozytorium rozdziela licencję danych CC0 od licencji kodu i modeli CC BY-NC. Zalecane cytowanie Wang et al., ACL-IJCNLP 2021. | 111 godzin i 282 mówców; naturalne wypowiedzi parlamentarne; udokumentowane pola `audio_id`, `raw_text`, `normalized_text`, `speaker_id`, `is_gold_transcript`. Pełny polski eksport HF ma ok. 20,6 GB. | **Źródło zweryfikowane, selektywny dostęp zablokowany** dla splitu `test`, rewizja `5ab868a7cddb87d84224ebfc8112ebd0905fc5bd`. |
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
mówcę. Każdy klip ma trwać 10–20 sekund, a suma 3–5 minut. Limit ruchu dla
audio i niezbędnych metadanych wynosi 25 MB. Osiągnięcie limitu przed uzyskaniem
pięciu mówców albo 180 sekund oznacza przerwanie, nie pobranie pełnego zbioru.

## Wynik weryfikacji przypięcia i dostępu

Oficjalne API Hugging Face potwierdziło istnienie przypiętej rewizji. Bieżąca
rewizja to `42f01879c780b4a2e90ec0b4f616c2ece526e4f1`, lecz całe drzewo `pl/` ma
identyczne ścieżki, rozmiary i identyfikatory obiektów jak rewizja przypięta.
Plik `pl/test-00000-of-00001.parquet` ma w obu rewizjach OID
`7139cfca3efa5f25d3f69b8b99d4144d84134a78` i 946 977 412 bajtów. Powiązanie
pochodzenia jest zatem potwierdzone.

Selektywny dostęp nie działa. `/rows` dla 100 i jednego rekordu zwraca HTTP
500, a `/first-rows` HTTP 501. Usługa wyjaśnia, że Parquet wymaga skanu
519 677 114 bajtów przy limicie 300 000 000 bajtów, ponieważ plik nie ma
indeksu stron lub wystarczająco małych grup wierszy. Bez pobrania 947 MB albo
nowego czytnika Parquet/Xet nie można sprawdzić faktycznej zawartości
`raw_text`, długości i relacji audio–referencja. Żadne audio nie zostało
pobrane, a finalne manifesty nie powstały.

Po osobnej zgodzie procedura będzie następująca:

1. potwierdzić rewizję, licencję danych i dostępność splitu `test`;
2. odczytać metadane małymi stronami, bez audio, i zachować tylko rekordy
   `is_gold_transcript`, z `raw_text` oraz pseudonimowym `speaker_id`;
3. nie wyszukiwać ani nie ustalać prawdziwej tożsamości mówców;
4. pobrać wyłącznie kandydatów, zatrzymując się przy 25 MB;
5. odrzucić klipy poza 10–20 s i wybrać pięć identyfikatorów mówców
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

Zadanie jest zatrzymane na przewidzianej bramce. Osobnej decyzji wymaga zmiana
źródła albo jawne zatwierdzenie nowego, ograniczonego mechanizmu odczytu
Parquet. Nie pobieramy pliku 947 MB, archiwum 20,6 GB ani Common Voice 4,49 GB
jako obejścia. Konwersja i późniejsza inferencja również wymagają osobnej zgody.
