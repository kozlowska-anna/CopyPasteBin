# Anonimizacja obrazów w CopyPasteBin 1.1

[English](image-redaction.md) | **Polski**

Ten dokument opisuje edytor obrazu dostępny w CopyPasteBin 1.1.

## Przebieg pracy

1. Wybierz **Anonimizuj obraz** w menu CopyPasteBin.
2. Otwórz lokalny plik PNG lub JPEG.
3. Przeciągnij prostokąt nad każdym wrażliwym obszarem. Podgląd używa tego
   samego nieprzezroczystego koloru, który zastąpi piksele.
4. W razie potrzeby cofnij ostatni prostokąt.
5. Zapisz nowy plik PNG.

Oryginał nigdy nie jest modyfikowany. Edytor odmawia również zastąpienia
innego istniejącego pliku docelowego. Prawidłowy wynik jest nowo zakodowanym
plikiem PNG bez metadanych kopiowanych ze źródła.

## Granica techniczna

Edytor obrazu jest osobnym procesem GJS/GTK 4 uruchamianym tylko na żądanie.
Korzysta z istniejącej w systemie biblioteki GdkPixbuf, dlatego nie dodaje
pakietu Python ani zależności sieciowej. Nie ma potoku stdin do rozszerzenia i
nie używa detektora tekstu, API schowka, API zrzutów ekranu, sieci ani
tymczasowego pliku obrazu.

Moduł przyjmuje wyłącznie lokalne zwykłe pliki, odrzuca dowiązania symboliczne
i ogranicza rozmiar skompresowanego pliku, wymiary oraz łączną liczbę pikseli
przed pełnym dekodowaniem. Wybrane prostokąty istnieją tylko w otwartym
procesie. Podczas zapisu program kopiuje zdekodowany bufor pikseli, zastępuje
każdy wybrany prostokąt nieprzezroczystymi pikselami, koduje świeży PNG w
pamięci i tworzy wyłącznie nowy prywatny plik docelowy.

## Świadomie poza zakresem

- OCR i automatyczne wykrywanie;
- wykonywanie zrzutów ekranu i obserwowanie katalogów;
- monitorowanie obrazów w schowku;
- rysowanie odręczne, rozmycie, pikselizacja i ogólny edytor grafiki;
- usługi sieciowe, telemetria i uprawnienia administratora.

## Weryfikacja

Testy automatyczne używają wyłącznie generowanych plików PNG i JPEG w
katalogach tymczasowych. Zakres wydania obejmuje uruchomienie edytora z menu,
wczytanie obrazu syntetycznego, zakrycie i cofnięcie prostokąta oraz zapis
nowego pliku PNG w docelowym środowisku GNOME Shell 50/Wayland.
