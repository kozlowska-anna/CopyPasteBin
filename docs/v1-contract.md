# CopyPasteBin V1 — zatwierdzony kontrakt

## Produkt

CopyPasteBin V1 składa się z lokalnego rdzenia analizy oraz lekkiego interfejsu
GNOME Shell 50. Aktualny UX jest zdarzeniowy i nie korzysta z pollingu
schowka. Stary watcher `wl-paste`, service i launcher usługi są legacy.

Program ostrzega i pomaga jawnie poprawić tekst. Domyślnie samo wykrycie nie
blokuje, nie usuwa ani nie zmienia schowka; osobną opcją jest czasowe
wyczyszczenie niezmienionego ostrzegającego wpisu.

## Wejście i limity

Jawne CLI przyjmuje dokładnie jedno źródło: stdin, zwykły plik albo schowek po
`--clipboard`. Interfejs GNOME pobiera wyłącznie tekstowy MIME po zdarzeniu
`owner-changed`. W obu przypadkach obowiązuje UTF-8 oraz limit 10 MiB; NUL,
zły UTF-8, nadmiar i niepełna ramka blokują operację.

Plik wejściowy musi być zwykłym plikiem otwartym z `O_NOFOLLOW`. Treść jest
analizowana w pamięci i nigdy wykonywana. Nie trafia do argv, env, logu,
publicznego błędu ani pliku tymczasowego.

## Kategorie i ryzyko

Reguły obejmują:

- e-mail, telefon, PESEL, IBAN, kartę płatniczą, klucz odzyskiwania,
  prywatną ścieżkę domową i adres IP;
- credentials w URL, Authorization/Basic/Bearer;
- klucz prywatny, klucze OpenAI/Anthropic/Google/Stripe/AWS, tokeny
  GitHub/Slack, JWT, ciągi połączeń baz danych i przypisania sekretów;
- tokenopodobne ciągi o wysokiej entropii;
- możliwe frazy seed/BIP-39;
- jawne kwoty 20 walut tradycyjnych i 20 kryptowalut;
- ograniczone lokalne reguły dosłowne `CUSTOM_RULE`.

Skala ma poziomy `critical`, `high`, `medium` i `low`; brak dopasowania ma
osobną wartość `none`. Klucze prywatne, recovery keys i frazy seed są
`critical`, sekrety uwierzytelniające `high`, e-mail i poprawny IBAN
`medium`, a słabsze heurystyki oraz kwoty `low`. Heurystyka nie jest dowodem
poprawności ani kompletności.

PESEL wymaga poprawnej sumy i możliwej zakodowanej daty, IBAN wyniku modulo 97,
a karta wyniku Luhna. Poprawny checksum nie dowodzi istnienia numeru.
Klucz odzyskiwania BitLocker wymaga pełnych 48 cyfr w ośmiu grupach. Każda
grupa musi mieścić się w zakresie formatu Microsoftu i być podzielna przez 11.
Ma poziom `critical` i nie jest równolegle opisywany jako telefon.
Inne formaty mają kategorię `RECOVERY_KEY` tylko przy jawnej etykiecie recovery
key/code/password albo „klucz odzyskiwania”; nie istnieje ogólne zgadywanie
każdego długiego identyfikatora.

Heurystyka telefonu nie klasyfikuje poprawnych dat kalendarzowych w formacie
rok–miesiąc–dzień albo dzień–miesiąc–rok jako numerów telefonu. Wyjątek jest
ograniczony do walidowanych dat i nie wyłącza wykrywania telefonu obok daty.
Nie dzieli też maksymalnego ciągu cyfr i separatorów na krótsze telefony.
Kandydat ma 7–15 cyfr i przechodzi kontrolę struktury oraz ograniczonego
kontekstu. Jawny prefiks `+` albo nawias pozostaje silnym sygnałem nawet obok
etykiety identyfikatora. W odrzuconym ciągu ponad 15-cyfrowym osobno
sprawdzane są tylko fragmenty objęte jawną etykietą telefonu albo mające własne
formatowanie. Etykieta identyfikatora obejmuje cały niejednoznaczny ciąg.

Kryptowaluta wymaga liczby oraz jawnego tickera, bez rozróżniania wielkości
liter. Sam ticker nie ostrzega. Program używa stałych list aktualizowanych z
wydaniami; nie sprawdza kursów, portfeli, transakcji ani blockchaina.

Dla 12/15/18/21/24 małych słów ASCII silnik rozróżnia poprawny checksum
BIP-39, słowa BIP-39 z błędnym checksumem oraz szerszą strukturę seed-like.
Wszystkie pozostają krytycznym ryzykiem. Lista 2048 słów jest lokalna,
wersjonowana i sprawdzana przez SHA-256 oraz inwarianty. Uszkodzenie zasobu
działa fail-closed.

Brak trafień zawsze oznacza wyłącznie:

> Nie wykryto znanych wzorców. To nie gwarantuje, że tekst jest bezpieczny.

## Analiza i jawne kopiowanie CLI

Wynik jawnej analizy zawiera kategorie, poziom i deterministycznie
zanonimizowany podgląd. `--copy redacted` zapisuje anonimizację do schowka.
`--copy original` dla wysokiego ryzyka wymaga jednorazowej frazy
`COPY <operation_id>` w tym samym procesie. Nie istnieje `--force`, `--yes`,
trwała zgoda ani dziedziczenie wyjątku przez duplikat.

## Historia

Techniczna retencja wynosi najwyżej 90 dni i 1000 rekordów. Interfejs pokazuje
najwyżej 8. Historia może przechowywać ID, czas, rodzaj źródła, cel, wersję
reguł, przedział rozmiaru, HMAC, relację duplikatu, kategorie, liczniki, ryzyko
i status.

Nie przechowuje oryginału, anonimizacji ani fragmentu wejścia. Deduplikacja
używa HMAC-SHA-256 z losowym kluczem `0600`; każda operacja dostaje nowe ID i
nie dziedziczy decyzji.

Zdarzenie GNOME zapisuje stabilny, ograniczony identyfikator aplikacji
źródłowej, jeżeli da się go wiarygodnie ustalić. Nie zapisuje tytułu okna,
nazwy dokumentu, URL, PID ani ścieżki procesu. Cel zwykłego kopiowania jest
`unknown`; sam fokus innego okna nie dowodzi wklejenia.

## Zdarzeniowy backend GNOME

Rozszerzenie subskrybuje tylko `Meta.Selection::owner-changed` dla schowka.
Nie ma timera odczytu ani globalnego hooka. Przed transferem sprawdza blokadę,
greeter i pauzę, wybiera MIME z zamkniętej listy i stosuje limit wejścia.
Po potwierdzeniu stanu aktywnego może pokazać 200-milisekundowy jasnoszary błysk
przedniej kartki ikony jako potwierdzenie zauważenia zmiany schowka. Błysk nie
jest wynikiem analizy, nie zmienia banerów i nie pojawia się podczas pauzy,
blokady ani dla własnej zmiany wykonanej przez edytor.

Treść przechodzi anonimowym stdin do stałego `cpb bridge observe`. Rdzeń
ponownie sprawdza pauzę, analizuje i zapisuje metadane. Odpowiedź ma najwyżej
2 KiB JSON i zawiera tylko wersję, ryzyko oraz kategorie z licznikami.

Zmiana właściciela z treścią identyczną jak ostatnio obsłużona lub właśnie
analizowana jest technicznym duplikatem. Rozszerzenie rozpoznaje ją po skrócie
SHA-256 przechowywanym wyłącznie w RAM i nie wysyła jej ponownie do mostu, nie
pokazuje drugiego bannera, nie dubluje historii ani listy ostatnich i nie
przesuwa automatycznego czyszczenia. Skrót znika przy blokadzie, wylogowaniu
lub wyłączeniu rozszerzenia. Jawne Bezpieczne wklejenie omija tę deduplikację.

`none` nie tworzy ostrzeżenia. `low`, `medium`, `high` i `critical` tworzą
własny baner bez treści, z kolorem zależnym od poziomu. Baner znika po 6 sekundach, może zostać
zamknięty, otwiera edytor i znika przy blokadzie. Kolejne zdarzenie zastępuje
poprzednie. Pozycja uwzględnia panel górny i dolny.

Pusty tekstowy schowek jest pokazywany jako niebieska informacja i nie oznacza
błędu ochrony. Nie jest analizowany ani zapisywany w historii. Rzeczywisty błąd
transferu, nadmiar lub niepotwierdzona ochrona pozostają czerwone.

Ikona używa trzech lokalnych SVG. Zielona tylna kartka oznacza dokładnie
potwierdzone `ACTIVE`; czerwona oznacza pauzę, przejście, błąd albo stan
niepotwierdzony.

## Pauza

Dozwolone są 30 minut, 1 godzina, tryb bezterminowy i jawne wznowienie.
Podczas pauzy rozszerzenie nie żąda treści, nie analizuje, nie ostrzega i nie
tworzy wpisu. Stan zawiera tylko tryb i opcjonalny termin w prywatnym pliku.

Po automatycznym albo ręcznym wznowieniu wartość zastana w schowku nie jest
analizowana wstecz; system czeka na następne kopiowanie. Zmiana pauzy podczas
otwartego edytora blokuje późniejszą sugestię lub zapis.

## Ustawienia filtrów

Każda z 17 zamkniętych kategorii może zostać osobno włączona lub wyłączona.
Przy braku wcześniejszego pliku ustawień wyłączone są `TOKEN`, `HOME_PATH` i
`POSSIBLE_SEED_PHRASE`; pozostałe filtry, w tym kategorie kluczy konkretnych
usług, są włączone. Krótka pozycja menu pokazuje liczbę aktywnych filtrów i
otwiera osobne przewijane okno z ptaszkiem przy każdej kategorii.
Zmiana zapisuje się od razu, a lista pozostaje czytelna niezależnie od
wysokości panelu i menu.

Wyłączona kategoria nie tworzy detekcji, ostrzeżenia ani licznika w nowym
wpisie i nie jest zastępowana przez sugestię anonimizacji. Pozostałe kategorie
w tym samym tekście nadal działają. Zmiana obejmuje kolejne zdarzenia i jawne
analizy, ale nie przepisuje historii.

Stan zawiera wyłącznie wersję, posortowane nazwy wyłączonych `Category` oraz
zamknięty czas automatycznego czyszczenia.
Plik jest atomowy, prywatny i nie zawiera danych schowka. Błędny albo
rozszerzony dokument działa fail-closed. Wyłączenie filtrów nie jest pauzą:
nie wyłącza obserwatora zdarzeń ani zapisu neutralnych metadanych kopiowania.

Opcjonalne automatyczne czyszczenie ma wartości: wyłączone, 1, 5 albo 15 minut.
Licznik powstaje tylko po ostrzeżeniu i jest związany z bieżącym numerem
zdarzenia. Nowe kopiowanie, edycja, pauza, zmiana opcji i wyłączenie komponentu
anulują go. Przed wyczyszczeniem ponownie sprawdzana jest pauza oraz niezmieniona
sekwencja. Mechanizm nie zapisuje treści ani jej skrótu na dysku. Ulotny skrót
potrzebny do rozpoznania technicznego duplikatu istnieje wyłącznie w RAM
bieżącej sesji.

## Edytor

Edytor GTK uruchamia się tylko na żądanie. Dostaje bieżący tekst stdin i
zwraca zatwierdzony wynik stdout. Schowek zmienia się dopiero po „Zastąp
schowek”; anulowanie i zamknięcie nie mają skutku.

„Anonimizuj wykryte dane” korzysta z tego samego silnika. Lokalne narzędzia
usuwają formatowanie i zbędne spacje, porządkują albo łączą wiersze, usuwają
puste wiersze, zmieniają wielkość liter oraz wykonują dosłowne znajdź/zamień.
Cofanie ma limit 50 kroków i istnieje tylko w pamięci procesu. Czyszczenie
schowka wymaga drugiego kliknięcia.

„Anonimizuj zaznaczenie” znajduje się w podręcznym menu otwieranym kliknięciem
wewnątrz jawnie zaznaczonego zakresu. Przetwarza wyłącznie ten zakres; reszta
tekstu, w tym inne wykryte wartości, pozostaje niezmieniona. Wynik nie jest
stosowany, jeżeli bufor zmienił się podczas analizy, a udane zastąpienie stanowi
jeden krok cofania. Kliknięcie podświetlonego trafienia otwiera to samo menu;
dla dopuszczalnego trafienia `low` lub `medium` zawiera ono również dokładne
„Wyklucz to trafienie”.

Edytor automatycznie wskazuje aktualne trafienia bursztynowym albo czerwonym
tłem. Po ręcznej zmianie usuwa stare oznaczenia; osobny przycisk ponawia
analizę. Kanał wynikowy niesie tylko pozycje, kategorię i poziom, nie treść.

Narzędzia edytora nie są ładowane ani wykonywane podczas zwykłego kopiowania.
Anonimizacja nie zapisuje treści ani dodatkowej operacji historii.

Osobne okno „Reguły własne i wykluczenia” pozwala dodać, edytować i usunąć do
32 dosłownych markerów oraz 32 dosłownych wykluczeń. Każdy wpis można wyłączyć
bez usuwania; reguła ma jeden z czterech poziomów ryzyka. Nie przyjmuje regexu.
Wykluczenie jest zależne od wielkości liter i usuwa wyłącznie detekcję o
identycznym zakresie, nie całą kategorię ani sąsiednie trafienia. Treść wpisów
jest zapisywana lokalnie w prywatnym `config.toml`, więc interfejs jawnie
zabrania używania prawdziwych haseł, kluczy, sekretów i innych rzeczywistych
danych wrażliwych jako wykluczeń.

Reguły i wykluczenia są widoczne jednocześnie w dwóch kolumnach. W obu
kolumnach aktywne i nieaktywne wpisy mają osobne, stale widoczne listy; widok
nie używa zwijanych sekcji ani koloru jako nośnika znaczenia.

Banner zwykłego ostrzeżenia może zaproponować wykluczenie jednej dokładnej
wartości. Funkcja ponownie pobiera wyłącznie pozycje detekcji, nie treść wyniku,
i otwiera istniejący edytor z wypełnionym formularzem. Użytkowniczka musi
sprawdzić widoczną wartość oraz kliknąć „Zapisz”. Szybka propozycja nie działa
dla `high`, `critical`, wielu różnych wykryć, wartości poza limitem 3–128 znaków ani tekstu
większego niż 256 KiB. Ręczne zarządzanie wykluczeniami pozostaje dostępne.

GUI ma angielski język bazowy i pełne polskie tłumaczenie. Użytkowniczka
wybiera język systemu, polski albo angielski w menu rozszerzenia. Wybór obejmuje
menu, banery, edytor schowka, filtry, ostatnie wpisy oraz okno reguł i
wykluczeń; jest trwały, lokalny i nie zmienia formatu danych ani wyniku
detekcji.

Rozszerzenie może przechować wyłącznie w RAM do 15 ostatnich tekstów, po
256 KiB i najwyżej 2 MiB łącznie. Większy tekst jest analizowany bez dodania do
listy. Osobne okno pokazuje bezpieczny podgląd, pozwala przywrócić wpis po
ponownej kontroli pauzy albo potwierdzonym drugim kliknięciem wyczyścić całą
listę. Nie istnieje zapis treści na dysk ani przywrócenie po zablokowaniu
ekranu, wyłączeniu rozszerzenia, wylogowaniu lub końcu sesji. Rozszerzenie nie
działa w trybie `unlock-dialog`; po odblokowaniu tworzy nową pustą listę.

## Wyjście i ponowne uruchomienie

„Wyjdź z CopyPasteBin” wymaga drugiego kliknięcia w ciągu 8 sekund. Wyłącza
wyłącznie własny UUID przez stałe argv i normalnie sprząta sygnały, transfer,
proces edytora, baner oraz timery. Nie odinstalowuje programu ani nie usuwa
historii.

Launcher aplikacji wykonuje wyłącznie
`/usr/bin/gnome-extensions enable copypastebin@kozlowska-anna.github.io`, bez terminala, shella,
starej usługi i watchera.

## Prywatność i prezentacja

Publiczne błędy są stałe i zredagowane. Modele z pozycjami detekcji mają
zredagowany `repr`. Podgląd terminalowy neutralizuje ANSI, C0/C1 i bidi.
Kanały prywatne są ograniczone. Migawka ostatnich wpisów ma limit 15 pozycji
i 2 MiB, a jej odpowiedź zawiera wyłącznie zamkniętą akcję i identyfikator.

Program nie używa sieci, nie przejmuje `Ctrl+V`, nie wykonuje wejścia, nie
wysyła tekstu i nie zgaduje celu. Nie chroni przed rootem, innym procesem tej
samego użytkownika, clipboard managerem, obserwacją ekranu, przejętą
aplikacją docelową ani false negatives.

## Legacy watcher i lifecycle

`cpb watch start`, `cpb service ...` i `cpb launcher setup` pozostają kodem
legacy. Są fail-closed i pokryte testami, lecz polling `wl-paste` na GNOME
Shell 50.1 kradł fokus przez tymczasową powierzchnię Wayland i zamykał menu
kontekstowe.

Legacy service ma pozostać nieaktywny, a dawny launcher nieobecny. Nie wolno
uznawać dłuższego interwału, dodatkowych prób, parsowania stderr ani zgadywania
po exit code za naprawę. Historyczny kontrakt pięciu prób, systemd i launchera
jest zachowany w kodzie i testach, ale nie jest alternatywnym trybem aktualnego
produktu.

## Poza V1

Chmura, synchronizacja urządzeń, OCR, obrazy i pliki binarne, rozszerzenie
przeglądarkowe, automatyczne modyfikowanie każdego kopiowania, auto-paste,
auto-send, globalny hook klawiatury oraz gwarancja wykrycia wszystkich danych.

Publiczne wydanie 1.0 korzysta z lokalnego archiwum offline. Snap rdzenia i
publikacja w GNOME Extensions są późniejszym etapem, nie częścią tego kanału
dystrybucji. Rozszerzenie ma stabilny publiczny UUID i angielski interfejs
bazowy z polskim tłumaczeniem.
