[English](README.md) | **Polski**

<img width="829" height="910" alt="CopyPasteBin_brochure_PL" src="https://github.com/user-attachments/assets/0c0491ce-3fa8-4026-affd-4699bce905e9" />

# CopyPasteBin

Materiały informacyjne: [broszura po polsku](docs/CopyPasteBin_brochure_PL.pdf)
oraz [broszura po angielsku](docs/CopyPasteBin_brochure_EN.pdf).

CopyPasteBin V1 jest lokalnym asystentem schowka dla GNOME. Rozpoznaje wybrane
rodzaje danych wrażliwych i sekretów, ostrzega przed ryzykiem oraz pomaga
świadomie zanonimizować tekst przed wklejeniem. Cała analiza odbywa się na
urządzeniu, bez wysyłania treści do chmury.

Program ogranicza ryzyko przypadkowego ujawnienia danych, ale nie zastępuje
oceny użytkownika. Brak ostrzeżenia oznacza jedynie, że CopyPasteBin nie
rozpoznał żadnego z aktywnych wzorców.

Autorką CopyPasteBin jest **Anna Kozłowska**. Projekt powstaje przy wsparciu
narzędzi ChatGPT i Codex od OpenAI. CopyPasteBin jest niezależnym projektem;
nie jest oficjalnym produktem ani projektem sponsorowanym przez OpenAI.

Copyright © 2026 Anna Kozłowska. Kod CopyPasteBin jest udostępniany na
licencji **GPL-3.0-or-later**; pełne warunki znajdują się w pliku `LICENSE`.
Informacje i warunki dotyczące danych stron trzecich znajdują się w pliku
`NOTICE` oraz w `docs/third-party-data.md`.

Historia zmian publicznych znajduje się w `CHANGELOG.md`.

Detektor rozróżnia `CRITICAL`, `HIGH`, `MEDIUM` i `LOW`. Rozpoznaje między
innymi klucze API OpenAI, Anthropic i Google, tokeny GitHub i Slack, klucze
Stripe i AWS, JWT, klucze prywatne oraz ciągi połączeń popularnych baz danych.
Całość działa lokalnie; dopasowanie nie potwierdza, że sekret jest aktywny.

## Aktualny stan

Aktualnym interfejsem jest lekkie rozszerzenie GNOME Shell 50. Reaguje na
`Meta.Selection::owner-changed`, a nie na timer. Przed pobraniem tekstu
sprawdza blokadę ekranu i pełną pauzę, po czym przekazuje ograniczoną treść do
lokalnego rdzenia przez anonimowe stdin. Nie używa sieci, nie przechwytuje
klawiatury i nie zgaduje celu wklejenia.

Gotowy zakres lokalnej wersji obejmuje:

- wykrywanie i deterministyczną anonimizację danych wrażliwych;
- czteropoziomowe ostrzeżenia we własnym kolorowym banerze;
- trwałą historię metadanych bez treści oraz podręczne 15 tekstów tylko w RAM;
- pauzę na 30 minut, 1 godzinę albo bezterminowo;
- osobne lekkie okno filtrów z widocznymi ptaszkami;
- jasne, klikalne pozycje filtrów i osobny lokalny edytor reguł oraz wykluczeń;
- jawny wybór dokładnego wykluczenia w edytorze schowka, otwierany także z bannera;
- wybór języka systemowego, polskiego albo angielskiego dla całego GUI;
- opcjonalne czyszczenie ostrzegającego schowka po 1, 5 albo 15 minutach;
- jawny edytor i narzędzia poprawiania tekstu uruchamiane tylko na żądanie;
- jawny skrót `Super+Shift+V` („Bezpieczne wklejenie”), który sprawdza bieżący
  tekst i przygotowuje propozycję redakcji bez automatycznego wklejania;
- potwierdzane czyszczenie schowka i wyjście z aplikacji;
- ikonę stanu: zielona tylna kartka oznacza aktywną ochronę, czerwona pauzę,
  przejście albo błąd;
- launcher „CopyPasteBin”, który włącza wyłącznie aktualne rozszerzenie.
- okno „O programie” z informacją o autorce, wersji, prywatności oraz wsparciu
  ChatGPT i Codexa.

Rdzeń CLI nadal obsługuje jawne wejście ze stdin, zwykłego pliku UTF-8 albo
jednorazowego `--clipboard`. Oryginał wysokiego ryzyka wymaga jednorazowej
frazy z ID i nie ma opcji `--force` ani `--yes`.

## Użycie

Publiczne polecenia rdzenia:

```text
printf 'tekst' | cpb --purpose chat
cpb --file JAWNY_PLIK --purpose email
cpb --clipboard --purpose drive
cpb pause 30m
cpb pause 1h
cpb pause until-resumed
cpb pause resume
cpb pause status
cpb history
cpb show ID
```

`--purpose` ma zamknięte wartości: `chat`, `email`, `drive`, `terminal`,
`other`. `--copy redacted` kopiuje wynik redakcji, a `--copy original`
oryginał zgodnie z polityką ryzyka. Tekst nie trafia do argv ani zmiennych
środowiskowych procesów schowka.

## Benchmark jakości detekcji

Deterministyczny benchmark używa wyłącznie syntetycznych przykładów i nie jest
częścią uruchomienia ani instalacji programu. Raportuje wykryte i pominięte
przypadki pozytywne oraz fałszywe alarmy osobno dla każdej badanej kategorii.
Ustalona baza wymaga zera pominięć i zera fałszywych alarmów; regresja kończy
polecenie niezerowym kodem:

```text
PYTHONPATH=src python3 benchmarks/detection_quality.py
```

Polecenia `bridge` i `ui` są wewnętrznym protokołem rozszerzenia, nie
interfejsem użytkownika.

## Język interfejsu

Menu rozszerzenia zawiera pozycję „Język / Language” z trzema ustawieniami:
język systemu, polski i angielski. Angielski jest językiem bazowym kodu GUI,
a polski wbudowanym tłumaczeniem. Zmiana obejmuje menu, banery oraz trzy okna
GTK: filtry, reguły i edytor schowka. Nowe okna otwierają się już w wybranym
języku.

Wybór jest lokalny dla użytkownika i zapisuje się w prywatnym pliku
`${XDG_STATE_HOME:-~/.local/state}/copypastebin/language.json`. Nie zawiera
treści schowka. Brak pliku oznacza język systemu; dla systemu innego niż
polski interfejs wybiera angielski. Upgrade i deinstalacja zachowują to
ustawienie tak samo jak pozostały prywatny stan.

## Aktualne uruchamianie GNOME

Kod rozszerzenia znajduje się w
`gnome-extension/copypastebin@kozlowska-anna.github.io`.
Zainstalowana lokalna wersja uruchamia się przy logowaniu, jeżeli rozszerzenie
ma stan enabled. „Wyjdź z CopyPasteBin” wyłącza je po drugim kliknięciu, a
launcher `packaging/copypastebin.desktop` wykonuje tylko:

```text
/usr/bin/gnome-extensions enable copypastebin@kozlowska-anna.github.io
```

Nie uruchamia terminala, usługi systemd ani watchera `wl-paste`.

## Bezpieczne wklejenie

Skrót `Super+Shift+V` jest rejestrowany przez rozszerzenie standardowym API
GNOME Shell. Wybrano go zamiast `Super+V`, ponieważ GNOME 50 domyślnie używa
`Super+V` dla zasobnika wiadomości. CopyPasteBin nie przechwytuje zwykłego
`Ctrl+V`, nie obserwuje całej klawiatury i nie emuluje naciśnięć klawiszy.

Po użyciu skrótu rozszerzenie sprawdza blokadę ekranu i pauzę, pobiera
ograniczony tekst schowka oraz uruchamia tę samą lokalną detekcję przez stdin.
Brak trafienia pokazuje krótkie potwierdzenie i nie zmienia schowka. Dla
`low`, `medium`, `high` i `critical` otwiera istniejący edytor z przygotowaną
propozycją redakcji; `high` i `critical` dostają dodatkowo wyraźny czerwony
komunikat i nigdy nie otrzymują trwałego wyjątku. Dopiero kliknięcie „Zastąp
schowek” zapisuje wynik. Anulowanie pozostawia schowek bez zmian. Funkcja nie
wkleja tekstu do aktywnej aplikacji i nie zna jej tytułu, dokumentu ani URL.

Skrót jest obecnie stały i ograniczony do jednego ustawienia GSettings
rozszerzenia. Rzeczywisty test działania wymaga GNOME Shell 50 po instalacji i
ponownym zalogowaniu; testy automatyczne nie stanowią LIVE PASS.

## Instalacja offline na drugim komputerze

Gotowy pakiet `CopyPasteBin-offline-linux-1.0.0.tar.gz` instaluje aktualną
wersję lokalnie dla jednego użytkownika. Nie wymaga `sudo`, nie korzysta z
sieci i nie przenosi konfiguracji, historii ani zawartości schowka z komputera,
na którym został zbudowany.

Obsługiwany komputer musi mieć GNOME Shell 50 na Waylandzie, Python 3.11 lub
nowszy z modułem `venv`, `gjs`, GTK 4 i narzędzie `gnome-extensions`.
Po rozpakowaniu należy najpierw wykonać bezpieczną kontrolę bez zmian:

```text
./install.sh --check-only
```

Jeżeli zakończy się wynikiem `Kontrola zgodności: OK`, instalację uruchamia:

```text
./install.sh
```

Instalator zachowuje inne włączone rozszerzenia, usuwa dawny roboczy UUID i
trwale dopisuje publiczny UUID CopyPasteBin. Następnie trzeba wylogować się i
zalogować ponownie do sesji GNOME Wayland; CopyPasteBin powinien uruchomić się
automatycznie. Jeżeli tak się nie stanie, przed użyciem pozycji z menu można
wykonać `./diagnose-first-activation.sh`. Raport pokazuje wyłącznie ograniczony
stan techniczny GNOME i niczego nie zmienia. `./uninstall.sh` usuwa kod,
rozszerzenie i launcher, ale zachowuje prywatne ustawienia oraz historię.
Szczegóły i granice opisuje `docs/offline-installation.md`.

## Kod legacy

`cpb watch start`, `cpb service ...` i `cpb launcher setup` pozostają w
repozytorium jako wcześniejsza, przetestowana ścieżka techniczna. Nie stanowią
aktualnego UX GNOME i nie powinny być używane w codziennej sesji. Polling
`wl-paste` na GNOME Shell 50.1 odbierał fokus i zamykał menu kontekstowe.
Zwiększenie interwału nie naprawia tej granicy. Stara usługa i dawny launcher
powinny pozostać nieaktywne; historię decyzji opisuje logbook.

Opcjonalny `${XDG_CONFIG_HOME:-~/.config}/copypastebin/config.toml` może
dodać najwyżej 32 dosłowne wzorce `CUSTOM_RULE` o jednym z czterech poziomów
ryzyka oraz najwyżej 32 dosłowne wykluczenia. Nie obsługuje regexów. Reguły i
wykluczenia można dodawać, edytować, czasowo wyłączać ptaszkiem i usuwać przez
pozycję „Reguły własne i wykluczenia” w menu głównym. Każde wykluczenie wiąże
dokładny literał z jedną kategorią `low` albo `medium`; kategorie `high` i
`critical` są odrzucane. Wykluczenie działa tylko dla dopasowania o dokładnie
takim samym zakresie i tej samej kategorii oraz rozróżnia wielkość liter:
np. `5.6 Sol` nie wyłącza `5.6 SOL`, `1 SOL` ani całej kategorii kryptowalut.
Okno pokazuje jednocześnie dwie kolumny — reguły i wykluczenia — a w każdej
stale widoczne sekcje aktywne i nieaktywne. Nic nie jest zwijane ani ukrywane.
Każdy banner ryzyka ma jeden przycisk „Otwórz edytor”. Kliknięcie dowolnego
miejsca w podświetlonym trafieniu automatycznie wybiera jego pełny zakres i
pokazuje podręczne akcje. „Wyklucz to trafienie” jest dostępne tylko wtedy, gdy
konkretne trafienie rzeczywiście można wykluczyć.
Przeciąganie nadal służy zwykłemu zaznaczaniu tekstu i nie otwiera dymka.
Zapis potwierdza małe okno ostrzegawcze z wyróżnioną akcją „Dodaj
wykluczenie”; `high` i `critical` nie mogą zostać wykluczone.
Jest to świadome osłabienie wykrywania wyłącznie dla wpisanej wartości, dlatego
nie należy wykluczać prawdziwych danych wrażliwych. Literały są zapisywane
lokalnie w prywatnym pliku; reguła powinna zawierać stabilny marker, nie sekret.

Format konfiguracji V3 dodaje kategorię do każdego wykluczenia. Przy odczycie
V2 program lokalnie wiąże stary wpis tylko wtedy, gdy cały literał daje jedno
jednoznaczne trafienie `low` lub `medium`. Wpisy niejednoznaczne, `high` i
`critical` nie są aktywowane; przy następnym jawnym zapisie edytora pozostają
pominięte. Migracja nie wymaga sieci ani osobnego odczytu schowka.

## Kwoty walut tradycyjnych i kryptowalut

Kategoria o stabilnym identyfikatorze `MONEY_AMOUNT_PLN_USD` ma poziom `low`
i obejmuje jawne kwoty z jednym z 20 kodów:
`USD EUR JPY GBP CNY CHF AUD CAD HKD SGD INR KRW SEK MXN NZD NOK TWD BRL ZAR PLN`.
Obsługiwane są też jednoznaczne symbole `$`, `€`, `£` oraz polskie `zł`.
Dotychczasowe kanoniczne formaty PLN i USD pozostają obsługiwane. Zwykła
liczba nie jest automatycznie kwotą. Nie ma konwersji, salda ani interpretacji
finansowej.

## Klucze odzyskiwania

Kategoria `RECOVERY_KEY` rozpoznaje 48-cyfrowe hasła odzyskiwania BitLocker:
osiem grup po sześć cyfr, opcjonalnie rozdzielonych spacjami albo myślnikami.
Każda grupa musi przejść lokalną kontrolę formatu Microsoftu — wartość nie
większą niż 720885 i podzielność przez 11. Trafienie ma wysokie ryzyko i jest
opisywane jako „klucz odzyskiwania”, a nie jako numer telefonu. Wyłączenie tego
filtra nie powoduje ponownego zaklasyfikowania tego samego zakresu jako telefonu.
Ta sama ogólna kategoria obejmuje również inne ciągi występujące po wyraźnej
etykiecie „Recovery key”, „Recovery code”, „Recovery password” albo „Klucz
odzyskiwania”. Bez takiego kontekstu program nie zgaduje dowolnych długich
identyfikatorów jako kluczy.

Heurystyka telefonu pomija poprawne daty kalendarzowe w formacie rok–miesiąc–
dzień albo dzień–miesiąc–rok, rozdzielone myślnikiem, kropką lub ukośnikiem.
Wyjątek wymaga rzeczywistej daty, więc nie obejmuje ciągów takich jak
`2026-13-40`. Telefon występujący obok daty nadal jest analizowany.
Kandydat telefonu jest oceniany jako cały ciąg cyfr i separatorów, ma od 7 do
15 cyfr oraz przechodzi kontrolę struktury i krótkiego kontekstu. Dzięki temu
długi identyfikator nie jest dzielony na kilka pozornych telefonów, a opisy
takie jak `ID`, `order` lub `numer seryjny` wyciszają tylko niejednoznaczne
formaty. Prefiks `+`, nawias kierunkowy i jawna etykieta telefonu pozostają
silnymi sygnałami wykrycia. Jeżeli odrzucony ciąg przekracza 15 cyfr, jego
fragmenty są analizowane osobno tylko przy jawnej etykiecie telefonu albo gdy
mają własne formatowanie, np. myślniki. Luźne grupy cyfr nie są automatycznie
składane w numery, a etykieta identyfikatora obejmuje cały niejednoznaczny ciąg.

Kategoria o stabilnym identyfikatorze `CRYPTO_AMOUNT_BTC_XRP` obejmuje 20
lokalnie zapisanych tickerów:
`BTC ETH USDT BNB XRP USDC SOL TRX HYPE ZEC DOGE XMR LINK LEO ADA XLM USDE DAI BCH USD1`.
Ticker musi wystąpić z liczbą; sam ticker nie wywołuje ostrzeżenia. Lista jest
aktualizowana wyłącznie wraz z wydaniami programu. CPB nie pobiera rankingu,
nie przelicza kursów, nie sprawdza adresów portfeli ani sieci blockchain.

## Frazy BIP-39

`POSSIBLE_SEED_PHRASE` ma zawsze wysokie ryzyko. Silnik rozróżnia poprawną
strukturę BIP-39 (pełna lokalna angielska lista i poprawny checksum), frazę
złożoną ze słów BIP-39 z błędnym checksumem oraz szerszą heurystykę seed-like.
Błędny checksum nie jest dowodem bezpieczeństwa. Brak albo uszkodzenie
wersjonowanej listy blokuje analizę. Pochodzenie i fingerprint zasobu opisuje
`docs/third-party-data.md`.

## Numery z sumą kontrolną

PESEL, IBAN i numery kart płatniczych mają osobne filtry. PESEL wymaga poprawnej
sumy oraz możliwej daty, IBAN przechodzi kontrolę modulo 97, a karta algorytm
Luhna. Poprawny checksum nie potwierdza, że numer istnieje lub należy do danej
osoby; ogranicza tylko przypadkowe alarmy dla zwykłych ciągów cyfr.

## Historia

Historia trafia do `${XDG_STATE_HOME:-~/.local/state}/copypastebin` z prawami
`0700`; baza i 256-bitowy klucz HMAC mają `0600`. Widok UX pokazuje najwyżej
8 pozycji. Retencja techniczna wynosi maksymalnie 90 dni i 1000 operacji.
Historia przechowuje tylko ID, czas, zamknięty rodzaj źródła i celu, wersję
reguł, przedział rozmiaru, HMAC, relację duplikatu, kategorie, liczniki,
poziom i status. Nie przechowuje oryginału, redakcji ani „niewinnego” wycinka.

Niezależnie od tej technicznej historii rozszerzenie trzyma podręcznie najwyżej
15 ostatnich skopiowanych tekstów wyłącznie w RAM. Limit jednego wpisu wynosi
256 KiB, a całości 2 MiB; większe teksty nadal są analizowane, lecz nie trafiają
na listę.
Pozycja „Ostatnie wpisy schowka” otwiera osobne okno GTK z bezpiecznym
podglądem, przywróceniem wybranej treści i potwierdzanym czyszczeniem całej
listy. Okno dostaje chwilową migawkę przez anonimowe stdin i zwraca tylko
zamknięty identyfikator akcji przez stdout. Treść nie trafia do pliku, argv,
env ani logu. Zablokowanie ekranu wyłącza rozszerzenie i usuwa listę z jego
pamięci; to samo następuje po wyłączeniu programu, jego awarii, wylogowaniu lub
końcu sesji. Po odblokowaniu lista zaczyna się od kolejnych kopiowań.
Środowisko uruchomieniowe nie gwarantuje kryptograficznego wyzerowania pamięci
ani wykluczenia swapu i hibernacji.

## Lekki interfejs GNOME

Lekki interfejs zachowuje trwałe metadane bez treści oraz ograniczoną,
sesyjną listę 15 tekstów w RAM, bez tytułów okien, nazw dokumentów i adresów
stron. Dla kopiowania zapisuje stabilny identyfikator aplikacji źródłowej,
jeżeli GNOME potrafi go wiarygodnie wskazać. Aplikacja docelowa pozostaje
`unknown` przy zwykłym wklejeniu i może zostać zapisana tylko dla jawnej
operacji wykonanej przez CopyPasteBin; zmiana fokusu nie jest dowodem
wklejenia.

Ostrzeżenie o danych wrażliwych jest doradcze. Domyślnie nie usuwa, nie redaguje
i nie blokuje treści automatycznie. Użytkowniczka może jednak jawnie włączyć
czyszczenie ostrzegającego schowka po 1, 5 albo 15 minutach. Licznik jest
anulowany przez nowe kopiowanie, edycję, zmianę ustawienia lub pauzę i czyści
tylko tę samą, niezmienioną sekwencję schowka. Treść ani jej hash nie są
zapisywane w ustawieniu.
Jawna akcja „Edytuj / anonimizuj schowek” otwiera małe okno z bieżącym
tekstem. Sugestia anonimizacji używa tego samego silnika reguł; użytkownik
może ją dalej zmieniać, a schowek jest zastępowany dopiero po kliknięciu
„Zastąp schowek”. Można zanonimizować wszystkie trafienia albo zaznaczyć tylko
wybraną wartość lub fragment tekstu, kliknąć wewnątrz zaznaczenia i wybrać
„Anonimizuj zaznaczenie” z podręcznego menu; pozostała treść nie zostanie wtedy
zmieniona. Kliknięcie podświetlonego trafienia pokazuje tę samą akcję, a dla
dozwolonego trafienia niskiego lub średniego ryzyka także dokładne wykluczenie.
Anulowanie nie zmienia schowka ani historii.

Rozwijana sekcja „Szybkie poprawianie tekstu” działa wyłącznie w otwartym
edytorze. Pozwala świadomie zapisać czysty tekst bez formatowania, zwinąć
nadmiarowe spacje, uporządkować albo połączyć wiersze, usunąć puste wiersze,
zmienić wielkość liter oraz wykonać dosłowne „znajdź i zamień”. Ostatnią
zmianę można cofnąć; wersje cofania istnieją tylko w pamięci procesu edytora
i znikają po zamknięciu okna. Te narzędzia nie dodają pracy do obsługi
kopiowania w tle. Osobny przycisk „Wyczyść schowek” wymaga drugiego kliknięcia
potwierdzającego i dopiero wtedy zastępuje jego zawartość pustym tekstem.
Przyciski anonimizacji wszystkich trafień, wskazania trafień i cofania pozostają
widoczne w jednym głównym rzędzie szerszego okna; anonimizacja zaznaczenia jest
w jego podręcznym menu, a cofanie uaktywnia się dopiero po zmianie tekstu.
Po otwarciu edytor wskazuje trafienia kolorami: bursztynowym dla ostrzeżenia
i czerwonym dla wysokiego ryzyka. Zmiana tekstu usuwa nieaktualne oznaczenia,
a „Wskaż wykryte dane” ponawia analizę na żądanie.

Gdy aktywny CPBin zauważy zmianę właściciela schowka, czarna przednia kartka
ikony na 200 ms zmienia kolor na jasnoszary `#E8E8E8`. Jest to wyłącznie
ciche potwierdzenie zauważenia kopiowania: nie zmienia oceny ryzyka ani banerów.
Kolejne szybkie kopiowanie przedłuża błysk, a pauza, blokada ekranu i własny
zapis z edytora go nie wywołują.

Ostrzeżenia zdarzeniowego interfejsu GNOME korzystają z własnego lekkiego
banera pod ikoną CPBin zamiast szarej notyfikacji systemowej. Ostrzeżenie ma
kolor bursztynowy, wysokie ryzyko czerwony, sukces zielony, a informacja
niebieski. Baner pokazuje wyłącznie nazwy zamkniętych kategorii i liczniki,
nigdy treść schowka; znika po 6 sekundach, może zostać zamknięty ręcznie albo
otworzyć edytor. Szybkie kolejne zdarzenie zastępuje poprzedni baner. Blokada
ekranu usuwa go natychmiast.
Położenie dopasowuje się do panelu: pod panelem górnym albo nad panelem dolnym,
z ograniczeniem do widocznego obszaru głównego monitora.

Menu zawiera również potwierdzane drugim kliknięciem „Wyjdź z CopyPasteBin”.
Wyjście wyłącza rozszerzenie, usuwa ikonę, baner, timery i obserwację schowka.
Pozycja „CopyPasteBin” w menu aplikacji włącza ponownie wyłącznie aktualne
rozszerzenie zdarzeniowe, bez terminala, starej usługi i watchera pollingowego.
Po ponownym uruchomieniu rozszerzenie pozostaje włączone także przy kolejnych
logowaniach; po wyjściu pozostaje wyłączone do użycia launchera.

Program ma pełną pauzę: 30 minut, 1 godzinę albo bezterminowo do ręcznego
wznowienia. Podczas pauzy nie czyta i nie analizuje schowka, nie wysyła
ostrzeżeń i nie zapisuje metadanych źródła ani celu. Po wznowieniu ignoruje
wartość pozostawioną w schowku podczas pauzy i czeka na następne kopiowanie.
Stan pauzy oraz pozostały czas muszą być stale widoczne; wznowienie czasowe
publikuje neutralne powiadomienie bez danych schowka.

Pozycja „Filtry wykrywania” pokazuje liczbę aktywnych ustawień i otwiera
osobne, przewijane okno wszystkich 17 kategorii. Włączone pozycje mają ptaszek,
a każda zmiana zapisuje się od razu.
Na świeżej instalacji wyłączone są „Token”, „Ścieżka domowa” i „Fraza seed”;
pozostałe filtry, w tym klucze konkretnych usług, są aktywne. Zmiana jest
trwała i wpływa na kolejne
ostrzeżenia, kategorie nowych wpisów historii, jawne analizy oraz sugestię
anonimizacji. Nie zmienia wcześniejszych wpisów. Plik ustawień zawiera tylko
zamknięte nazwy wyłączonych kategorii oraz wybrany czas czyszczenia, nigdy
treść schowka.

Budżet UX pozostaje mały: przetwarzanie zdarzeniowe bez pollingu, brak sieci,
brak globalnego podsłuchiwania klawiatury, najwyżej 15 tekstów i 2 MiB w RAM
oraz okna historii i edycji otwierane wyłącznie na żądanie.

Polecenia `cpb pause ...` zapisują bezpieczny stan pauzy konsumowany przez
zdarzeniowe rozszerzenie GNOME. Pollingowy watcher nie jest uruchamiany i nie
należy traktować tych poleceń jako naprawy jego regresji GNOME.

Repozytorium zawiera działające rozszerzenie GNOME 50 łączące wskaźnik pauzy
z natywnym zdarzeniem zmiany schowka. Pobiera wyłącznie tekst, najwyżej 10 MiB,
poza pauzą i ekranem blokady. Do historii zapisuje metadane źródła oraz cel
`unknown`, bez treści. Nowa wersja lokalnego rozszerzenia zaczyna działać po
ponownym zalogowaniu do sesji Wayland; wyłączenie i włączenie w tej samej sesji
nie gwarantuje przeładowania kodu z dysku.

Ikona ma dwie zachodzące na siebie kartki. Przednia pozostaje czarna z jasnym
obrysem, a częściowo widoczna tylna kartka pokazuje stan: zielony oznacza
aktywną ochronę, czerwony pauzę, zmianę stanu albo błąd/stan niepotwierdzony.

Podręczna historia treści otwiera osobne okno na żądanie i przekazuje jego
migawkę wyłącznie anonimowym stdin. Edytor jest uruchamiany tylko na żądanie;
oryginał i wynik sugestii przechodzą przez anonimowe stdin/stdout, nigdy przez
argv, env ani plik tymczasowy. Edytor i zapis ponownie sprawdzają pełną pauzę.

## Granice

CopyPasteBin nie używa sieci, nie wykonuje wejściowego tekstu, nie wysyła go
do aplikacji i nie przejmuje `Ctrl+V`. Zdarzeniowy backend nie wkleja ani nie
wysyła treści. Zmiana schowka następuje po jawnej akcji w edytorze albo przez
jawnie włączone czasowe czyszczenie ostrzegającego wpisu. Program nie gwarantuje wykrycia wszystkich sekretów ani
kryptograficznego wyzerowania pamięci Pythona. Szczegółowy kontrakt i model
zagrożeń są w `docs/v1-contract.md` i `SECURITY.md`.
