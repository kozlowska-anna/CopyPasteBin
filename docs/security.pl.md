# Model bezpieczeństwa CopyPasteBin V1

**Polski** | [English](../SECURITY.md)

## Chronione dane

Oryginalny tekst, dane osobowe i finansowe, sekrety, wynik anonimizacji oraz
klucz HMAC nie mogą trafić do trwałej historii, logów, błędów, `repr`, argv,
env ani plików tymczasowych. Jawny wyjątek stanowi ograniczona sesyjna lista
ostatnich tekstów przechowywana wyłącznie w RAM rozszerzenia. Podgląd
terminalowy neutralizuje ANSI, C0/C1 i znaki bidi.

Aktualną ścieżką pulpitu jest zdarzeniowe rozszerzenie GNOME Shell 50. Stary
watcher `wl-paste`, usługa systemd i dawny launcher są kodem legacy i mają
pozostać nieaktywne.

## Granice techniczne

- brak sieci, chmury, auto-send i auto-paste;
- brak `shell=True`, `eval`, `exec`, wykonywania wejścia i otwierania URL;
- brak globalnego hooka klawiatury i przejmowania `Ctrl+V`;
- pojedynczy skrót `Super+Shift+V` rejestrowany przez standardowe
  `Main.wm.addKeybinding`, aktywny tylko w `Shell.ActionMode.NORMAL`;
- UTF-8, limit 10 MiB, odrzucenie NUL i nadmiaru;
- zwykły plik wejściowy otwierany z `O_NOFOLLOW`;
- stdin/stdout zamiast tekstu w argv, env i pliku tymczasowym;
- historia używa HMAC-SHA-256, nie zwykłego skrótu treści;
- ustawienia filtrów przechowują tylko zamknięte nazwy kategorii i wybrany
  czas automatycznego czyszczenia;
- treść jawnie utworzonej reguły własnej jest wyjątkiem: musi być lokalnie
  zapisana, dlatego interfejs ostrzega, aby nie wpisywać prawdziwego sekretu;
- poziomy `high` i `critical` nie mają skrótu trwałego ani automatycznego wyjątku;
- błędy publiczne są stałe i nie publikują przyczyny wyjątku.

Program nie chroni przed rootem, innym procesem tego samego użytkownika,
systemowym clipboard managerem, obserwacją ekranu, przejętą aplikacją docelową,
false negatives ani kopiami pozostawionymi w pamięci interpretera.

## Zdarzenie GNOME i transfer

Rozszerzenie reaguje wyłącznie na
`Meta.SelectionType.SELECTION_CLIPBOARD::owner-changed`. Przed transferem
sprawdza blokadę, greeter i pełną pauzę. Dopuszcza zamkniętą listę tekstowych
MIME i pobiera najwyżej 10 MiB + 1 bajt.

Źródło zdarzenia jest ograniczonym identyfikatorem aplikacji. Nie zapisujemy
tytułu okna, nazwy dokumentu, URL, PID, ścieżki procesu ani dowolnej
nieograniczonej wartości dostarczonej przez aplikację.

Ramka do `cpb bridge observe` przechodzi anonimowym stdin i zawiera tylko
ograniczony identyfikator oraz tekst. Most odrzuca złą długość, niepełną ramkę,
nadmiar, zły UTF-8, NUL i pusty tekst, a następnie ponownie sprawdza pauzę.

Odpowiedź stdout ma najwyżej 2 KiB i zamknięty JSON: wersja, ryzyko oraz
kategorie z licznikami. Nie zawiera treści, redakcji, pozycji dopasowań ani ID
operacji. Rozszerzenie waliduje całość przed pokazaniem banera.

Udany transfer tekstowego MIME o długości zero nie jest wysyłany do mostu i nie
tworzy historii. Pokazuje wyłącznie niebieską informację o pustym schowku.
Nieudany transfer i przekroczenie limitu pozostają błędem fail-closed.

## Historia, podręczna pamięć i deduplikacja

Historia zapisuje wyłącznie metadane, techniczny HMAC i relację duplikatu.
Nie przechowuje oryginału, anonimizacji ani „niewinnego” fragmentu. Widok ma
limit 8, techniczna retencja 90 dni i 1000 rekordów.

Prywatny katalog stanu ma prawa `0700`, a baza, klucz HMAC i stan pauzy
`0600`. Symlinki, obcy właściciel i niewłaściwe prawa są odrzucane w
bezpiecznych magazynach. Klucz HMAC jest losowy i lokalny.

Cel zwykłego kopiowania pozostaje `unknown`. Zmiana fokusu nie jest dowodem
wklejenia i nie uzupełnia historii.

Rozszerzenie przechowuje dodatkowo do 15 ostatnich tekstów, najwyżej 256 KiB na
wpis i 2 MiB łącznie. Wpis powstaje dopiero po udanej walidacji odpowiedzi
mostu, więc pauza, ekran blokady, pusty lub niepoprawny transfer i błąd analizy
nie dodają treści. Tekst nie trafia do Pythona ponownie, bazy ani pliku stanu.

Osobne okno GTK otrzymuje chwilową migawkę binarną przez stdin. Zwraca przez
stdout wyłącznie zamkniętą akcję i nietreściowy identyfikator wpisu; błędy są
wyciszane i redagowane. Przywrócenie ponownie sprawdza pauzę i blokadę ekranu.
Wyłączenie rozszerzenia kończy okno i usuwa referencje do wpisów. JavaScript,
swap, hibernacja i zrzuty procesu oznaczają, że nie jest to kryptograficzne
wymazanie ani gwarancja, że bajty nigdy nie dotkną nośnika.

Rozszerzenie celowo nie deklaruje trybu GNOME `unlock-dialog`. Blokada ekranu
wyłącza je przez standardowy lifecycle GNOME, a `disable()` usuwa listę RAM.
Po odblokowaniu powstaje nowa, początkowo pusta lista. Dzięki temu kod CPB nie
pozostaje aktywny na ekranie blokady kosztem utraty podręcznej historii.

## Detekcja

Poziomy ryzyka mają kolejność `critical > high > medium > low`; brak trafienia
jest osobnym stanem `none`. Klucze prywatne, recovery keys i frazy seed są
`critical`; rozpoznane sekrety uwierzytelniające są `high`; e-mail i poprawny
IBAN są `medium`; słabsze heurystyki i kwoty są `low`.

Biblioteka sekretów ma osobne, wyłączalne kategorie dla kluczy OpenAI,
Anthropic i Google, tokenów GitHub i Slack, kluczy Stripe i identyfikatorów
dostępu AWS, JWT oraz ciągów połączeń baz danych. JWT wymaga trzech segmentów i
dekodowalnego nagłówka JSON z algorytmem innym niż `none`. Reguły są offline,
nie próbują użyć klucza i nie sprawdzają jego aktywności. Ogólna heurystyka
entropii pozostaje zabezpieczeniem uzupełniającym i może dawać false positives.

Lista BIP-39 jest lokalnym zasobem. Kod sprawdza jej SHA-256, dokładnie 2048
unikalnych słów, porządek i checksum frazy. Uszkodzenie działa fail-closed;
błędny checksum frazy nadal pozostaje wysokim ryzykiem.

Hasło odzyskiwania BitLocker jest rozpoznawane wyłącznie jako pełne 48 cyfr
w ośmiu grupach. Każda grupa musi być nie większa niż 720885 i podzielna przez
11, zgodnie z formatem Microsoftu. Dopasowanie ma krytyczne ryzyko i zajmuje cały
zakres przed heurystyką telefonu. Wyłączenie filtra `RECOVERY_KEY` nie odsłania
na nowo nakładających się dopasowań telefonu.
Inne formaty mogą trafić do tej kategorii tylko przy jednoznacznej etykiecie
recovery key/code/password albo „klucz odzyskiwania”. Sam nieopisany ciąg nie
jest uznawany za taki klucz wyłącznie na podstawie długości lub entropii.

Kwoty 20 wspieranych kryptowalut wymagają liczby oraz jawnego tickera. Reguła
nie łączy się z siecią, nie odpytuje kursów ani blockchaina i nie interpretuje
samego tickera jako danych finansowych. Lista 20 walut tradycyjnych pochodzi z
zamkniętego zestawu kodów i nie uruchamia przeliczeń ani pobierania kursów.

PESEL przechodzi sumę kontrolną i walidację zakodowanej daty, IBAN kontrolę
modulo 97, a numer karty algorytm Luhna. Kontrola ogranicza false positives,
ale nie potwierdza istnienia, aktywności ani właściciela numeru.

Heurystyka telefonu najpierw obejmuje maksymalny ciąg cyfr i obsługiwanych
separatorów, a dopiero potem waliduje 7–15 cyfr, położenie `+`, nawiasy,
grupowanie i krótki kontekst. Nie wycina krótszych telefonopodobnych fragmentów
z długiego identyfikatora. Etykiety identyfikatora wyciszają tylko formaty
niejednoznaczne; numer z prefiksem `+` albo nawiasem nadal jest analizowany.
Jest to heurystyka offline, a nie potwierdzenie istnienia lub właściciela
numeru. W odrzuconym ciągu dłuższym niż 15 cyfr silnik odzyskuje rozdzielone
spacją fragmenty tylko przy jawnej etykiecie telefonu albo ich własnym
formatowaniu. Etykieta identyfikatora wyłącza taki drugi przebieg. Silnik nie
próbuje dowolnie łączyć krótkich grup w potencjalne telefony.

Reguły niestandardowe są dosłownymi markerami z limitem liczby i długości.
Każda może pozostać zapisana, ale być wyłączona flagą boolean.
Nie przyjmują regexu ani kodu. Osobne dosłowne wykluczenia świadomie osłabiają
reguły wbudowane wyłącznie dla detekcji o dokładnie takim samym zakresie i tej
samej zapisanej kategorii. Dozwolone są tylko kategorie o poziomie `low` lub
`medium`; `high` i `critical` są odrzucane także w rdzeniu, niezależnie od GUI.
Wykluczenia rozróżniają wielkość liter, nie wyłączają całej kategorii i nie
ukrywają sąsiedniego trafienia. Interfejs ostrzega przed wykluczaniem
prawdziwych danych wrażliwych.
Edytor reguł działa wyłącznie po jawnej akcji, przekazuje ograniczony JSON
przez stdin/stdout i zapisuje atomowo `config.toml` jako `0600` w katalogu
`0700`. Treść reguł nie trafia do historii ani komunikatów błędów.

Przycisk wykluczenia na bannerze `low` lub `medium` nie wybiera ani nie zapisuje
ukrytej wartości: otwiera edytor schowka. Edytor pokazuje pozycje wykrytego
tekstu. Pojedyncze kliknięcie wewnątrz trafienia `low` lub `medium` wybiera
znany pełny zakres 3–128 znaków bez znaków sterujących i pokazuje lokalny
dymek z kategorią; ruch wskaźnika większy niż ustalona tolerancja pozostaje
zwykłym zaznaczaniem i nie uruchamia akcji. Dymek otwiera modalne potwierdzenie
z domyślną akcją anulowania i wyróżnioną akcją dodania. Przed zapisem edytor
ponownie sprawdza rewizję tekstu, zakres, kategorię, ryzyko i literał. Wartość
przechodzi do ograniczonego polecenia
`ui exclusion-add` przez stdin, nigdy przez argv, env, log ani plik tymczasowy.
Odpowiedź zawiera tylko zamknięty status bez treści. Rdzeń ponownie sprawdza
kategorię, długość, znaki sterujące, konflikt i limit; `high` i `critical` są
odrzucane niezależnie od GUI.

Konfiguracja V3 zapisuje przy wykluczeniu literał, kategorię i stan aktywności.
Migracja V2 jest konserwatywna: stary literał jest importowany wyłącznie wtedy,
gdy sam daje jedno pełnozakresowe trafienie `low` lub `medium`. Stare wpisy
niejednoznaczne oraz wysokiego i krytycznego ryzyka są ignorowane, a przy
następnym jawnym zapisie usuwane. Odczyt, migracja i zapis zachowują limit,
atomowy plik `0600`, katalog `0700` i odmowę pracy na dowiązaniach.

Wybór języka GUI jest oddzielnym stanem o zamkniętych wartościach `system`,
`pl` i `en`. Prywatny `language.json` nie zawiera treści schowka, reguł ani
historii; podlega tym samym kontrolom właściciela, praw i symlinków co inne
pliki stanu. Do procesów okien trafia wyłącznie efektywny kod `pl` albo `en`.

Brak dopasowania nie jest deklaracją bezpieczeństwa.

## Bezpieczne wklejenie

`Super+V` pozostaje skrótem GNOME do zasobnika wiadomości, dlatego jawna akcja
CopyPasteBin używa `Super+Shift+V`. Rozszerzenie rejestruje jedną nazwę
keybindingu z własnego, zamkniętego schematu GSettings. Nie korzysta z
globalnego hooka, `grab_accelerator`, emulacji klawiszy ani przechwytywania
`Ctrl+V`. `disable()` zawsze usuwa keybinding, anuluje aktywną analizę i zwalnia
jej proces.

Akcja sprawdza lock/greeter i pauzę przed odczytem oraz ponownie przed
pokazaniem wyniku. Tekst trafia tylko przez stdin do `cpb ui detections`, a
odpowiedź zawiera wyłącznie ograniczone pozycje, kategorie i poziomy. `none`
nie zmienia schowka. Pozostałe poziomy otwierają istniejący edytor, który
lokalnie prosi o propozycję redakcji; wynik istnieje w jego pamięci i wraca do
rozszerzenia dopiero po jawnym zapisie. `high` i `critical` nie mają w tej
ścieżce wykluczenia. Anulowanie, błąd, pauza lub blokada nie zapisują schowka.

Funkcja nie wykonuje wklejenia i nie ustala aplikacji docelowej, tytułu okna,
nazwy dokumentu ani URL. Nie zwiększa limitu 15 ostatnich wpisów w RAM i nie
tworzy nowego daemona, timera odczytu ani trwałej historii treści.

## Pauza

Pauza jest odcięciem odczytu, nie wyciszeniem notyfikacji. Przez 30 minut,
1 godzinę albo do ręcznego wznowienia rozszerzenie nie żąda treści, nie
analizuje, nie ostrzega i nie zapisuje zdarzeń.

Stan pauzy zawiera tylko wersję, tryb i opcjonalny termin. Po wznowieniu
wartość zastana w schowku nie jest analizowana wstecz. Pauza jest sprawdzana
przed transferem, w moście, przed otwarciem edytora, sugestią i zapisem.

## Baner i ikona

Baner jest lokalnym aktorem `St`. Pokazuje wyłącznie zamknięte nazwy kategorii
i liczniki; nie używa systemowego `notify-send` w aktualnej ścieżce. Znika po
6 sekundach, przy ręcznym zamknięciu, zastąpieniu kolejnym zdarzeniem lub
blokadzie ekranu.

Wyłączenie usuwa baner, timer oraz sygnał trybu sesji. Nie używać
`affectsInputRegion` z `Main.layoutManager.addChrome` na GNOME Shell 50.1;
ten nieobsługiwany parametr wcześniej powodował błąd rozszerzenia.

Zielony wariant ikony pojawia się wyłącznie po dokładnie potwierdzonym
`ACTIVE`. Pauza, przejście i błąd pozostają czerwone fail-closed.
Po potwierdzeniu `ACTIVE` zmiana właściciela schowka może na 200 ms przełączyć
wyłącznie lokalny wariant SVG z jasnoszarą przednią kartką. Sygnał nie niesie
treści, kategorii ani wyniku analizy, nie powstaje na ekranie blokady i jest
sprzątany razem z rozszerzeniem. Nie zastępuje banerów ryzyka.

## Edytor i zapis schowka

Edytor GTK uruchamia się tylko na jawną akcję i dostaje tekst stdin. Wynik
wraca stdout do rozszerzenia, które pozostaje właścicielem zapisu schowka.
Anulowanie lub zamknięcie niczego nie zmienia.

Sugestia anonimizacji korzysta z tego samego silnika przez `cpb ui redact`.
Tryb zaznaczenia przekazuje tym samym ograniczonym kanałem wyłącznie jawnie
zaznaczony fragment i zastępuje tylko ten zakres. Jeżeli tekst zmieni się przed
zakończeniem analizy, wynik jest odrzucany zamiast stosowany do nieaktualnej
pozycji. Zmiana jest grupowana jako jeden krok cofania.
Pozycje trafień dla jawnego podświetlenia wracają przez osobny ograniczony
JSON bez dopasowanej treści. Edycja tekstu usuwa nieaktualne znaczniki.
Narzędzia tekstowe i ograniczone cofanie działają wyłącznie w pamięci procesu
edytora. Czyszczenie wymaga drugiego kliknięcia. Pauza ustawiona podczas
otwartego edytora blokuje późniejszą sugestię lub zapis.

Rozszerzenie pomija jedno własne zdarzenie po zapisie, aby nie tworzyć
dodatkowego wpisu ani ostrzeżenia. Mechanizm ma ograniczony timeout i jest
sprzątany przy wyłączeniu.

Kolorowe oznaczenia używają jawnych obiektów GTK4 `TextTag` dodanych do tabeli
bufora; błąd aktywacji okna nie może pozostawać traktowany jako widoczny
edytor. Proces jest czyszczony po każdym zakończeniu komunikacji. Ponowne
kliknięcie podczas działania wysyła stały `SIGUSR1`, obsługiwany lokalnie przez
edytor wyłącznie jako prośba o `present()` istniejącego okna; nie niesie danych.

## Ustawienia filtrów

Stan filtrów jest prywatnym JSON-em `0600` w katalogu stanu `0700`. Zawiera
tylko wersję, kanoniczną listę wyłączonych wartości `Category` i jedną z
zamkniętych wartości czasu: 0, 60, 300 albo 900 sekund. Bez pliku domyślnie
wyłączone są `TOKEN`, `HOME_PATH` i `POSSIBLE_SEED_PHRASE`; pozostałe
kategorie są włączone. Nieznana kategoria,
duplikat, nadmiar, symlink, obcy właściciel lub niewłaściwe prawa blokują
odczyt i analizę danego przepływu zamiast zgadywać konfigurację.

Polecenia UI mają zamknięte argumenty kategorii oraz `on|off`; nie przyjmują
tekstu schowka. Odpowiedź ma limit 2 KiB, pełną ustaloną listę i wartości
boolean. Osobny proces GTK pokazuje wyłącznie publiczne etykiety, ptaszki oraz
licznik; każdą zmianę zapisuje pojedynczo i blokuje kolejne kliknięcia do
otrzymania zweryfikowanej odpowiedzi.

Świadome wyłączenie kategorii osłabia zakres wykrywania zgodnie z decyzją
użytkownika. Licznik jest widoczny w menu, a pełny stan w oknie; działa spójnie w
backendzie, jawnej analizie oraz anonimizacji. Nie usuwa wcześniejszych wpisów
i nie jest odpowiednikiem pauzy.

## Opcjonalne automatyczne czyszczenie

Domyślną wartością jest 0, czyli brak automatycznej zmiany schowka. Po jawnym
wybraniu 1, 5 albo 15 minut licznik powstaje po każdym wyniku od `low` do
`critical`. Rozszerzenie przechowuje wyłącznie numer sekwencji zdarzenia i timer,
nie treść ani jej hash. Każda zmiana właściciela schowka, jawna edycja, zmiana
ustawienia, pauza lub wyłączenie rozszerzenia anuluje licznik. Przed samym
czyszczeniem ponownie sprawdzana jest pauza i numer sekwencji; dopiero wtedy
schowek zostaje ustawiony na pusty tekst. Funkcja nie oferuje kryptograficznego
wymazywania pamięci ani kontroli kopii zapisanych przez inne clipboard managery.

## Wyjście i launcher

Wyjście wymaga drugiego kliknięcia w ciągu 8 sekund. Używa stałego
`/usr/bin/gnome-extensions disable <własny UUID>` bez shella i danych
użytkownika. Normalne `disable()` odłącza sygnały, anuluje transfer, kończy
edytor i usuwa UI oraz timery.

Aktualny launcher wykonuje wyłącznie `/usr/bin/gnome-extensions enable
copypastebin@kozlowska-anna.github.io`, ma `Terminal=false` i nie przyjmuje
plików ani URI. Nie uruchamia starej usługi, `watch start`, sudo ani
dynamicznego polecenia.

Instalator utrwala ten sam publiczny UUID w `org.gnome.shell
enabled-extensions`, ponieważ GNOME może jeszcze nie rozpoznawać świeżo
skopiowanego rozszerzenia w bieżącej sesji. Pomocnik używa lokalnego
`Gio.Settings`, zachowuje wszystkie obce wpisy, usuwa wyłącznie roboczy UUID
`copypastebin@local` i nie wypisuje odczytanej listy. Nie używa sieci, usługi,
opóźnienia ani dostępu do schowka. Opcja `--no-enable` pomija tę zmianę.

## Jawne CLI

Jawny odczyt i zapis schowka w CLI korzystają ze stałych argv, `shell=False`,
ograniczonego stdout i tekstu przekazywanego do zapisu tylko przez stdin.
Oryginał wysokiego ryzyka wymaga jednorazowego porównania stałoczasowego z
`COPY <operation_id>`; odmowa i awaria aktualizują tylko metadane statusu.

## Kod legacy

`cpb watch start`, `cpb service ...` i `cpb launcher setup` są wcześniejszą,
pokrytą testami architekturą. Pollingowy odczyt `wl-paste` na GNOME Shell 50.1
używał tymczasowej powierzchni Wayland, odbierał fokus i zamykał menu
kontekstowe. Dlatego nie jest aktualnym trybem produktu.

Legacy watcher zachowuje fail-closed, stałe argv, ograniczony startup grace,
prywatny `flock`, zredagowane błędy i `Restart=no`, ale nie wolno go
uruchamiać równolegle ani przywracać przez dawny launcher. Stara usługa ma
pozostać zatrzymana i nieobecna. Nie naprawiamy tej ścieżki przez dłuższy
interwał, więcej prób, parsowanie stderr albo zgadywanie exit code.

Kontrakt historycznego lifecycle jest zachowany w kodzie i testach, ale nie
stanowi alternatywnego trybu aktualnego produktu.

## Publikacja

Rozszerzenie ma stabilny publiczny UUID oraz angielską bazę komunikatów z
polskim tłumaczeniem. Pierwsze wydanie publiczne jest dystrybuowane jako
lokalne archiwum offline z zewnętrzną sumą SHA-256. Publikacja w GNOME
Extensions i osobne, confined pakowanie rdzenia wymagają późniejszego review i
nie należą do zakresu 1.0. Licencja projektu została ustalona jako
`GPL-3.0-or-later`, a nota BSD-3-Clause dla danych BIP-39 jest zachowana w
dystrybucji. Pozostałe prace nie mogą osłabić opisanych wyżej granic
prywatności.

