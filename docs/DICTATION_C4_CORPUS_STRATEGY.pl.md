# CopyPasteBin 1.3 — C4: organizacja korpusów polskiego STT

Status: **decyzja projektowa i plan pilotażu; bez pobierania nowego audio**.
Data przeglądu: 2026-11-16.

## Zamknięcie oceny ParlaSpeech

Piętnaście zachowanych nagrań ParlaSpeech jest poprawnych strukturalnie:
pochodzenie, rozmiary, format i sumy SHA-256 zostały sprawdzone, a konwersję
wykonano lokalnie bez sieci. Nie wystarcza to jednak do pomiaru WER/CER.

Ręczny odsłuch wykazał różnice między wypowiedzianymi słowami a oficjalnymi
tekstami. W dodatkowej pięcioelementowej grupie kontrolnej wszystkie pięć
referencji zawierało pominięcia, dodatki albo redakcyjne zamiany słów. Zgłoszono
także pogłos dużej sali, nagłośnienie, oklaski i przedłużone dźwięki. Te
obserwacje nie dowodzą, że każdy klip ParlaSpeech jest wadliwy, lecz wystarczają,
aby nie używać tego źródła jako podstawowego wzorca dosłownej transkrypcji.

Decyzja:

- ParlaSpeech nie jest podstawowym korpusem naturalnego dyktowania;
- istniejących plików, hashy i manifestów nie usuwamy, nie nadpisujemy ani nie
  przenosimy;
- zachowane 15 nagrań ma rolę `acoustic-challenge-candidate`;
- ich bieżące teksty mają status `source-original-unverified` i nie mogą być
  podstawą wiarygodnego WER/CER;
- tagi `reverberant`, `applause`, `noisy` i `reference_mismatch` przypisuje się
  wyłącznie konkretnym klipom po odsłuchu, nigdy całemu zbiorowi z założenia;
- ewentualna przyszła korekta zachowa tekst źródłowy obok osobnej referencji
  ludzkiej i będzie wymagała niezależnej weryfikacji.

## Kandydaci na podstawowy korpus

| Źródło | Licencja i dostęp | Mocne strony | Ograniczenia | Ocena |
| --- | --- | --- | --- | --- |
| PWr-AZON, część nadzorowana | CC BY-SA 4.0; publiczny, selektywny podgląd wierszy w repacku Hugging Face; oryginał wskazany w metadanych | Wielu mówców, nagrania czytane do mikrofonu, ścieżki części nadzorowanej zawierają identyfikator mówcy, można pobrać kilka rekordów zamiast całego zbioru | Repack nie jest wydawcą oryginału; teksty i identyfikatory trzeba sprawdzić z dokumentacją PWr; część materiału jest specjalistyczna, a dosłowność referencji nie jest jeszcze potwierdzona odsłuchem | **Najlepszy kandydat do małego pilotażu** |
| Common Voice Scripted Speech 27.0 PL | CC0; oficjalna dystrybucja Mozilla Data Collective; zakaz identyfikowania mówców i ponownego hostowania | 139 352 zwalidowane klipy i 3477 mówców; nagrania z mikrofonów użytkowników; głosy i urządzenia bliskie rzeczywistemu użyciu | Oficjalny pakiet ma 4,49 GB, średni klip 4,573 s, materiał jest czytany, a dostęp do małej odtwarzalnej próbki nie jest obecnie zapewniony bez pobrania archiwum lub dodatkowego dostępu | Najlepszy kandydat szeroki, lecz nie do pierwszej próby minimalnej |
| CLARIN-PL Mobile Corpus | CC BY 3.0; jedno archiwum 1,44 GB | Wielu mówców, tekst czytany, 13 godzin; środowisko telefoniczne pozwala badać zwykłe urządzenia | Telefonia nie odpowiada mikrofonowi komputera; brak małego oficjalnego pakietu; nadal wymaga kontroli dosłowności | Rezerwa po rozwiązaniu selektywnego dostępu |
| CLARIN-PL Studio Corpus | CC BY 3.0; około 4,9 GB w kilku plikach | Wielu mówców, czytelne nagrania i kontrolowane teksty | Studio jest zbyt czyste względem typowego dyktowania; duży transfer | Korpus kontrolny, nie główny |
| FLEURS `pl_pl` | CC BY 4.0; publiczne wiersze i selektywne audio | Mały pilotaż jest technicznie prosty; nagrania czytane i przeznaczone do ewaluacji ASR | Publiczny schemat nie ma identyfikatora mówcy; polska część ma tylko kilku mówców i teksty tłumaczone, więc różnorodność i naturalność są ograniczone | Rezerwa do kontroli technicznej |
| BIGOS V2 | Otoczka CC BY-SA 4.0 oraz licencje źródeł; dostęp na Hugging Face wymaga akceptacji warunków | Ujednolica 12 polskich źródeł, wiele domen i mówców, format ewaluacyjny | 27,8 GB, dostęp bramkowany; karta podaje, że bieżące referencje są oryginalnymi transkrypcjami, a ręczne transkrypcje podzbiorów były planowane | Katalog i punkt odniesienia, nie źródło pierwszego pilotażu |
| PELCRA/Spokes Mix | Zależnie od części CC BY albo CC BY-NC; formularz i hasło dostępu | Naturalne rozmowy, wielu mówców, transkrypcje słowo po słowie i znaczniki zdarzeń | Rozmowa wieloosobowa nie przypomina dyktowania; nowe konto lub formularz, zróżnicowane licencje i akustyka | Kandydat do przyszłego benchmarku rozmów/trudnych warunków |

Źródła:

- <https://huggingface.co/datasets/czyzi0/pwr-azon-speech-dataset>
- <https://zasobynauki.pl/zasoby/korpus-nagran-probek-mowy-do-celow-budowy-modeli-akustycznych-dla-automatycznego-rozpoznawania-mowy,53293/>
- <https://mozilladatacollective.com/datasets/cmu5wsxwp00e0nq07m8v0274j>
- <https://commonvoice.mozilla.org/cv/guidelines?tab=scripted-speech>
- <https://clarin-pl.eu/dspace/items/92004353-58c3-49f0-97d9-66edf1cf1095>
- <https://clarin-pl.eu/dspace/items/cd3f6380-97e6-488f-9a91-c228df5c4ac6>
- <https://huggingface.co/datasets/google/fleurs>
- <https://huggingface.co/datasets/amu-cai/pl-asr-bigos-v2>
- <https://github.com/poleval/2024-asr-bigos>
- <https://docs.pelcra.pl/doku.php?id=spoken_offline_corpora>

## Rekomendowany test wstępny

Pierwszym wyborem jest wyłącznie **pilotaż części nadzorowanej PWr-AZON**, nie
zatwierdzenie źródła do benchmarku.

1. Przypiąć rewizję repacku i potwierdzić pochodzenie oraz CC BY-SA 4.0 w
   oryginalnym rekordzie PWr/AZON.
2. Na podstawie metadanych wybrać 12 kandydatów: cztery pseudonimowe katalogi
   `Speakers/<id>`, po trzy klipy, najlepiej 6–15 sekund. Nie zapisywać nazw ani
   nie próbować ustalać tożsamości.
3. Preferować zwykłe zdania i mowę do mikrofonu; odrzucić muzykę, oklaski,
   nakładające się głosy, bardzo specjalistyczne wyliczenia oraz niejednoznaczne
   skróty i liczby.
4. Przed audio sprawdzić host, przypiętą rewizję, format, rozmiar i limit
   łącznego transferu. Proponowany limit pilotażu: 10 MB.
5. Po osobnej zgodzie pobrać tylko wybrane pliki, zapisać źródłowe SHA-256 i
   przygotować lokalną stronę odsłuchową. Nie uruchamiać STT.
6. Każdy klip ocenić ręcznie: dosłowność, jeden mówca, pogłos, hałas, muzyka,
   oklaski, przesterowanie i podobieństwo do dyktowania.
7. Do dalszego etapu przechodzi co najmniej osiem dokładnie zgodnych klipów:
   po dwa od czterech mówców. Mniejszy wynik oznacza odrzucenie źródła, a nie
   ręczne dopasowywanie tekstu do celu.

Próbka celowo ma zapas czterech klipów. SHA-256 potwierdzi integralność, ale nie
zastąpi odsłuchu audio–referencja.

## Dwa niezależne benchmarki

### `natural-dictation-pl-v1`

Podstawowy zestaw do WER, CER, RTF i opóźnień. Zawiera wyłącznie klipy z jednym
mówcą, małym pogłosem, bez muzyki i oklasków oraz referencją
`reference-verified`. Docelowo powinien zawierać wielu mówców i nagrania z
urządzeń zbliżonych do mikrofonu komputera.

### `acoustic-challenge-pl-v1`

Oddzielny zestaw odporności na pogłos, nagłośnienie, hałas, oklaski i zmienną
odległość. ParlaSpeech pozostaje kandydatem do tego zestawu. Klip z
`source-original-unverified` może służyć do pomiarów wydajności, lecz nie do
WER/CER. Jakość liczymy dopiero po uzyskaniu zweryfikowanej referencji.

Manifesty i wyniki mają być osobne. Planowane pola organizacyjne:

- `benchmark_suite`: `natural-dictation-pl-v1` albo
  `acoustic-challenge-pl-v1`;
- `acoustic_tags`: lista obserwacji, np. `clean`, `reverberant`, `applause`,
  `noisy`; `clean` nie może współwystępować z tagiem trudnych warunków;
- `reference.kind`: `source-original` albo `human-corrected`;
- `reference.status`: `unverified`, `verified` albo
  `pending-independent-review`;
- `reference.review`: data, pseudonim recenzenta i metoda odsłuchu, bez danych
  prywatnych.

Raport tworzy osobne sekcje i osobne agregaty dla obu zestawów:

- WER i CER tylko dla referencji `verified`;
- RTF, inicjalizacja, `completed_ms`, CPU i RSS dla każdego zestawu;
- liczba klipów wyłączonych z jakości z powodu niezweryfikowanej referencji;
- wyniki według faktycznie potwierdzonych tagów akustycznych.

Nie wolno łączyć obu zestawów w jedną średnią opisywaną jako ogólna jakość
polskiego STT. Dotychczasowe wyniki Tatoeba pozostają historyczną kontrolą
adapterów i nie są przepisywane.

## Wiarygodność referencji

1. `source-original`: tekst dostarczony przez źródło, zachowywany bez zmian.
2. `human-corrected`: osobny tekst przygotowany wyłącznie z odsłuchu, nigdy z
   hipotezy Vosk, Whisper ani innego ocenianego modelu.
3. `unverified`: tekst, którego zgodności słowo w słowo nie potwierdzono.

Korekta ludzka otrzymuje status `pending-independent-review`. Dopiero drugi
odsłuch, bez podglądu wyników STT, może nadać `verified`. Oryginał, korekta,
uzasadnienie zmiany i identyfikator pliku pozostają rozdzielone. Kategoria
`unverified` nigdy nie trafia do mianownika WER/CER.

## Bezpieczeństwo

**Korzyść:** mały pilotaż pozwoli sprawdzić dosłowność i akustykę przed dużym
transferem oraz przed pracą natywnego kodu STT.

**Nowy dostęp:** tylko publiczne metadane i — po osobnej zgodzie — maksymalnie
12 wskazanych plików audio. Nie potrzeba mikrofonu, schowka, historii CPB,
tokenu, nowego konta ani instalacji systemowej.

**Ryzyka:** błędne pochodzenie repacku, niedokładna transkrypcja, wygasające
adresy, nieoczekiwany rozmiar oraz przypadkowe utrwalenie jawnej etykiety
mówcy.

**Zabezpieczenia:** przypięta rewizja, porównanie z oryginalnym rekordem,
zamknięta lista rekordów, limit 10 MB, HEAD bez przekierowań, SHA-256, katalog
`0700`, pliki `0600`, brak nazw w Git, konwersja bez sieci w `bwrap`, ręczny
odsłuch przed inferencją i brak wysyłania audio do usług chmurowych.

**Mniejszy zakres:** obecny etap kończy się na raporcie. Nie pobrano nowego
audio, nie użyto tokenu ani konta, nie zmieniono implementacji benchmarku i nie
uruchomiono inferencji.
