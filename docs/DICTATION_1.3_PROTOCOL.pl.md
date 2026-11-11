# CopyPasteBin 1.3 — protokół i bezpieczna integracja dyktowania

Status: zaimplementowany prototyp C1–C3 bez dostępu do mikrofonu  
Data: 2026-11-11

Ten dokument opisuje bieżący kod oraz granicę dalszej integracji. Prototyp nie
instaluje silnika ani modelu, nie otwiera urządzenia audio, nie używa sieci i
nie zmienia schowka bez dotychczasowego przycisku zatwierdzenia.

## Stan implementacji

- `dictation-session.js` waliduje zamknięty protokół ramek i utrzymuje stany
  `unavailable`, `idle`, `starting`, `recording`, `stopping`, `error`.
- Edytor ma widoczny przycisk mikrofonu i lokalny
  `Gtk.ShortcutController` dla `Super+Shift+R`. Rozszerzenie GNOME Shell nie
  rejestruje tego skrótu globalnie.
- W zwykłym uruchomieniu kontrolka jest nieaktywna, ponieważ nie istnieje
  jeszcze zatwierdzony backend STT. Jawna deweloperska flaga
  `--dictation-simulation` uruchamia wyłącznie ustaloną sekwencję syntetyczną.
- Tekst częściowy jest osobnym podglądem. Wynik końcowy trafia do
  `Gtk.TextBuffer` jako jedna odwracalna akcja w miejscu ruchomego znacznika.
  Nowy częściowy wynik zastępuje poprzedni podgląd i nie zmienia ręcznie
  poprawionego tekstu.
- Zamknięcie edytora anuluje sesję i usuwa zaplanowane wyniki symulacji.
  Zapis do schowka jest wyłączony w stanach aktywnej sesji.

## Protokół wyników workera

Każda wiadomość jest pojedynczym obiektem JSON. Implementacja ogranicza ramkę
do 8192 bajtów, tekst do 4096 znaków, identyfikator sesji do 64 bezpiecznych
znaków i odrzuca pola spoza zamkniętego schematu.

```json
{"version":1,"session_id":"session-1","sequence":1,"kind":"ready"}
{"version":1,"session_id":"session-1","sequence":2,"kind":"partial","segment":0,"text":"To jest"}
{"version":1,"session_id":"session-1","sequence":3,"kind":"final","segment":0,"text":"To jest test."}
{"version":1,"session_id":"session-1","sequence":4,"kind":"stopped"}
{"version":1,"session_id":"session-1","sequence":4,"kind":"error","code":"engine"}
```

Dozwolone kody błędów to `audio-device`, `engine`, `protocol` i `worker`.
Identyfikator sesji odrzuca spóźnione wyniki poprzedniego workera, rosnący
`sequence` odrzuca powtórzenia ramek, a numer `segment` zapobiega ponownemu
dodaniu zatwierdzonego fragmentu. Błąd walidacji ma stały komunikat bez treści
transkrypcji.

Worker produkcyjny powinien być osobnym, nieuprzywilejowanym procesem potomnym
edytora. Audio ma płynąć w pamięci, a wyniki przez ograniczony pipe. Proces nie
może być usługą, demonem ani dzieckiem GNOME Shell. Polecenia start/stop i
transport audio nie są jeszcze zaimplementowane; przed ich dodaniem potrzebny
jest wybór silnika i jawna zgoda na dostęp do mikrofonu.

## Wskaźniki stanu

Obecny prototyp zmienia przycisk mikrofonu na niebieski wyłącznie w stanie
`recording`; czerwony nie oznacza nagrywania. Stan `stopped` jest zdarzeniem
protokołu kończącym sesję i przechodzi do `idle`.

Propozycja dla panelu, jeszcze niewdrożona:

1. kartki nadal pokazują wyłącznie stan ochrony schowka;
2. podczas rzeczywistego nagrywania obok kartek pojawia się osobny mały
   niebieski mikrofon;
3. zatrzymanie usuwa mikrofon zamiast zmieniać kolor kartek;
4. kombinacje są niezależne: niebieskie kartki + niebieski mikrofon oznaczają
   ochronę i nagrywanie, a czerwone kartki + niebieski mikrofon — pauzę
   monitoringu i dyktowanie w przyszłym pustym edytorze.

Nie należy zmieniać logiki ikony panelu przed istnieniem rzeczywistej sesji
audio i niezawodnego kanału stanu między edytorem a rozszerzeniem.

## Pusty edytor podczas pauzy

Bezpieczny projekt rozdziela dwa jawne tryby uruchomienia:

- `clipboard`: obecny tryb, który wymaga aktywnej ochrony i dopiero potem
  odczytuje schowek;
- `blank`: tworzy pusty bufor bez wywołania API schowka i może działać podczas
  pauzy.

Tryb `blank` nie jest jeszcze wdrożony. Wymaga osobnego typu wyniku i
jednoznacznej kontrolki „Kopiuj wynik”, ponieważ obecna ścieżka „Zastąp
schowek” ponownie sprawdza pauzę. Jawne kopiowanie z pustego edytora może być
dozwolone jako działanie użytkownika, ale nie może wznawiać monitoringu,
odczytywać starej zawartości ani dodawać tekstu do historii. To jest zmiana
semantyki wymagająca osobnego testu i zatwierdzenia.

## Porównanie kandydatów

Nie ma jeszcze wyniku benchmarku na docelowym sprzęcie, więc nie wybrano
silnika.

| Kandydat | Dowody z dokumentacji | Pytanie do pomiaru |
| --- | --- | --- |
| Vosk `small-pl-0.22` | model polski 50 MB, Apache-2.0; API strumieniowe; małe modele zwykle ok. 300 MB RAM | jakość polskiej interpunkcji i dokładność w dyktowaniu |
| whisper.cpp `tiny/base/small` | modele 75/142/466 MiB i ok. 273/388/852 MB RAM; MIT; lokalny przykład `stream` przelicza audio co 0,5 s i jest opisany jako naiwny | opóźnienie stabilnego tekstu, jakość polska i koszt CPU |

Vosk ma lepiej dopasowaną semantykę wyników częściowych. Whisper jest
uzasadnionym kandydatem jakościowym, ale sam przykład strumieniowy nie dowodzi,
że jego korekty będą wystarczająco szybkie i stabilne. Zgodność z Ubuntu 26.04
i Fedorą 44 pozostaje niezweryfikowana. Harness
`experiments/dictation-benchmark/` jest gotowy do WER/CER, opóźnień, CPU, RSS
i rozmiaru modelu, lecz nie uruchamia silnika ani mikrofonu.

Źródła: [Vosk — modele](https://alphacephei.com/vosk/models),
[Vosk — API offline i streaming](https://alphacephei.com/vosk/),
[whisper.cpp — README](https://github.com/ggml-org/whisper.cpp/blob/master/README.md),
[whisper.cpp — licencja](https://github.com/ggml-org/whisper.cpp/blob/master/LICENSE),
[OpenAI Whisper — modele i licencja](https://github.com/openai/whisper/blob/main/README.md).

## Dalsze uprawnienia i zabezpieczenia

Następny etap wymaga osobnej zgody na pobranie kodu silnika i modeli. Plan
powinien wskazać dokładne URL-e, sumy SHA-256, rozmiary, licencje, katalog
docelowy i polecenia instalacyjne bez `sudo`. Model pozostaje opcjonalny.

Rzeczywista integracja wymaga dostępu tylko do wejścia audio podczas jawnej
sesji. Musi zatrzymywać worker przy zamknięciu, blokadzie sesji, uśpieniu,
utracie urządzenia i awarii procesu; nie może zapisywać audio ani transkrypcji,
logować treści, korzystać z sieci ani kopiować wyniku automatycznie. Te
przypadki nie są spełnione przez sam prototyp symulacyjny i muszą otrzymać
testy integracyjne przed pierwszą paczką z mikrofonem.

Docelowy manager modeli powinien używać wersjonowanej allowlisty zawierającej
silnik, język, wersję, rozmiar, URL HTTPS, SHA-256 i licencję. Pobieranie jest
jawne, plik częściowy ma prywatne uprawnienia i limit rozmiaru, a instalacja
następuje atomowo po weryfikacji. Usuwanie nie podąża za symlinkami i dotyczy
wyłącznie wpisu z allowlisty w katalogu danych użytkownika.
