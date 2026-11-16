# CopyPasteBin 1.3 — C4: plan korpusu naturalnej polskiej mowy

Status: **ParlaSpeech odrzucony jako podstawowy wzorzec WER/CER; 15 WAV zachowano
jako kandydatów do oddzielnego benchmarku trudnych warunków**.
Data decyzji po ręcznym odsłuchu: 2026-11-16.

Aktualna decyzja, porównanie alternatyw i plan dwóch niezależnych benchmarków
znajdują się w `DICTATION_C4_CORPUS_STRATEGY.pl.md`. Poniższe sekcje zachowują
historię selekcji, pobrania i walidacji strukturalnej ParlaSpeech; nie stanowią
już zatwierdzenia tego źródła do podstawowego benchmarku jakości.

Dotychczasowy korpus Tatoeba, jego manifest i wyniki pozostają niezmienione.
Nowy etap ma sprawdzić dłuższą mowę wielu osób, a nie wyłonić zwycięzcę STT.

## Ocena źródeł

| Źródło | Licencja i autorstwo | Przydatność | Decyzja |
| --- | --- | --- | --- |
| ParlaSpeech-PL 1.0 | Audio i transkrypcje: CC BY-SA 4.0; autorzy Danijel Koržinek i Nikola Ljubešić; wydawca Jožef Stefan Institute/CLARIN.SI. Źródłem są transkrypcje ParlaMint 4.0 i nagrania polskiego parlamentu. | Naturalna mowa parlamentarna, oficjalne redagowane transkrypcje i automatyczne dopasowanie segmentów; ręczny odsłuch wykazał rozbieżności słowo w słowo oraz trudną akustykę. | **Nie jest źródłem podstawowym**. Zachowane 15 rekordów pozostaje kandydatem do benchmarku trudnych warunków z referencjami niezweryfikowanymi. |
| VoxPopuli, polski ASR | Dane audio i transkrypcje: CC0; źródłowe nagrania Parlamentu Europejskiego. | 111 godzin i 282 mówców, ale Dataset Viewer nie może przeskanować testowej grupy wierszy w swoim limicie. | Źródło zweryfikowane, **selektywny dostęp zablokowany** dla przypiętej rewizji. |
| Common Voice Scripted Speech 27.0 PL | CC0; zakaz prób ustalania tożsamości mówców i ponownego hostowania zbioru. | 4,49 GB w jednym oficjalnym archiwum; głównie krótkie wypowiedzi czytane. | Odłożone: pobranie całości narusza zasadę minimalizacji dla 15 próbek. |
| FLEURS `pl_pl` | CC BY 4.0; atrybucja korpusu FLEURS/Google i publikacji. | Selektywny dostęp jest możliwy, lecz schemat publiczny nie zawiera identyfikatora mówcy, a domeną jest mowa czytana. Polski config ma ok. 2,05 GB. | Rezerwa, **nie jest liczona** do minimum różnych mówców. |

Źródła informacji:

- <https://hdl.handle.net/11356/1686>
- <https://huggingface.co/datasets/classla/ParlaSpeech-PL>
- <https://clarinsi.github.io/parlaspeech/>
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

## Wynik selekcji ParlaSpeech-PL

Oficjalny rekord CLARIN.SI potwierdza licencję CC BY-SA 4.0, autorów, wydawcę
oraz powiązanie zdań z transkrypcjami ParlaMint 4.0. Repozytorium Hugging Face
zostało przypięte do rewizji
`88887ee82cdb7e3f20e7b29d4c1740d0bc630f41`. Każdy sprawdzony adres audio
zawiera tę rewizję w ścieżce.

Przeskanowano 420 rekordów metadanych od offsetu zero. Kandydat musiał mieć
10–20 sekund, niepusty `text` i `text_normalised`, typ `audio/flac` oraz etykietę
mówcy. Nazwy służyły wyłącznie do tymczasowego grupowania i nie zostały
zapisane. Pierwszych pięciu mówców z co najmniej trzema kandydatami otrzymało
pseudonimy `speaker-01`–`speaker-05`; wybrano trzy rekordy o najniższych
indeksach każdego mówcy.

Pierwotnie wybrany rekord 97 był niedostępny; po jawnej zgodzie zastąpiono go
rekordem 99 tego samego mówcy. Ostateczne 15 rekordów ma łącznie 195,74 s.
Wszystkie mają niepuste referencje z interpunkcją. HEAD zwrócił HTTP 200 bez
przekierowań dla każdego rekordu; łączny rozmiar wynosi 3 871 015 bajtów.

Pobrano dokładnie te 15 plików FLAC do prywatnego katalogu `0700`; pliki i
lokalny manifest SHA-256 mają tryb `0600`. Rozmiary, typ `audio/flac` i SHA-256
zostały ponownie sprawdzone lokalnie. FLAC zdekodowano w `bwrap` bez sieci i
przekonwertowano GStreamerem do mono PCM WAV 16-bit, 16 kHz. Powstało 15 WAV o
łącznym rozmiarze 6 264 344 bajty i rzeczywistym czasie 195 740,125 ms.

Prywatny manifest przeszedł walidator wersji 3: 15 próbek, pięciu mówców,
format, uprawnienia, SHA-256, czas i komplet kategorii wraz z jawnymi brakami.
Jeden surowy tekst (`natural-pl-14`) zawierał komentarz parlamentarny; dla
całego korpusu konsekwentnie użyto oficjalnego `text_normalised`, który zachował
interpunkcję. Nie uruchomiono inferencji ani urządzeń audio. Automatyczne
dopasowanie segmentu do referencji nadal wymaga ludzkiego odsłuchu, więc
manifest pozostaje prowizoryczny.

## Historyczna blokada VoxPopuli

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

## Zamknięta procedura selekcji

Zatwierdzona procedura ParlaSpeech jest następująca:

1. potwierdzić rewizję i licencję w autorytatywnym rekordzie CLARIN.SI;
2. odczytać metadane od offsetu zero stronami po najwyżej 100 rekordów;
3. użyć jawnych etykiet mówców tylko tymczasowo, przypisać pseudonimy i nie
   zapisywać nazw ani transkrypcji w Git;
4. przed audio sprawdzić HEAD, host, rewizję w URL, brak przekierowania, typ i
   dodatni rozmiar każdego pliku;
5. pobrać dokładnie wybrane pliki, zatrzymując się przy 25 MB;
6. zapisać hash źródła, a po kolejnej zgodzie przekonwertować GStreamerem do
   mono PCM WAV 16 kHz i zapisać drugi hash;
7. skopiować tekst referencyjny z przypiętych metadanych; nigdy z wyniku STT.

Plan slotów znajduje się w
`audio-manifest.natural-pl.plan.json`, a oddzielny, celowo nieuruchamialny plan
referencji w `cases.natural-pl.plan.json`. Po pobraniu powstaną osobne pliki
`audio-manifest.natural-pl.json` w wersji 3 i `cases.natural-pl.json` w wersji
1. Audio i transkrypcje wynikowe nie trafią do Git.

## Pokrycie i ograniczenia

ParlaSpeech dobrze pokrywa dłuższą naturalną wypowiedź, liczby i daty, nazwy
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
`validate_natural_audio_manifest.py` wymusza 15 próbek, dokładnie pięć
pseudonimowych slotów mówców, dozwolone licencje, przypięte rewizje, SHA-256,
format WAV, czas,
kategorie, katalog `0700`, pliki `0600` i zgodność jeden-do-jednego z
referencjami.

Pobranie, SHA-256, izolowane dekodowanie, konwersja i walidacja strukturalna są
zakończone. Do finalizacji pozostaje ręczna kontrola 15 par audio–referencja i
potwierdzenie rzeczywistego pokrycia planowanych kategorii. Inferencja nadal
wymaga osobnej zgody.
