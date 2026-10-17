# Dane stron trzecich

## Angielska lista słów BIP-39

Plik `src/copypastebin/data/bip39_english.txt` zawiera 2048 angielskich słów
BIP-39. Został skopiowany bez sieci z lokalnego pakietu Ubuntu
`python3-passlib` (`python-passlib` 1.9.3-1ubuntu1), z pliku
`/usr/lib/python3/dist-packages/passlib/_data/wordsets/bip39.txt`. Dokumentacja
tego pakietu identyfikuje zasób jako opublikowany w ramach Bitcoin BIP-39.
Pakiet jest udostępniany na licencji BSD-3-Clause.
Pełna nota copyright i tekst tej licencji są zachowane w repozytoryjnym pliku
`NOTICE`, który jest również dołączany do paczki offline i wheelu.

Źródłowy plik pakietu miał SHA-256
`24ce42c2fd4a95c1b86bbee9bce1e1cf255bd0022e19bab6bd591afd68b7efdb`.
W repozytorium lista jest znormalizowana do jednego słowa na wiersz i jednego
końcowego znaku LF; jej SHA-256 to
`2f5eed53a4727b4bf8880d8f3f199efc90e58503646d9ff8eff3a2ed3b24dbda`.
Kod sprawdza ten skrót, liczbę 2048 unikalnych słów i ich kanoniczny porządek.
Brak albo zmiana zasobu blokuje analizę zamiast wyłączać ochronę.

## Zamknięte listy kodów walut

Lista walut tradycyjnych została ustalona na podstawie tabeli D11.3 Banku
Rozrachunków Międzynarodowych „Turnover of OTC foreign exchange instruments,
by currency”, dane za kwiecień 2025 opublikowane w finalnym zestawie 2026:
https://data.bis.org/topics/DER/tables-and-dashboards/BIS,DER_D11_3,1.0

Wbudowana kolejność 20 kodów to:
`USD EUR JPY GBP CNY CHF AUD CAD HKD SGD INR KRW SEK MXN NZD NOK TWD BRL ZAR PLN`.

Lista kryptowalut jest zamkniętym snapshotem 20 pierwszych pozycji według
kapitalizacji z CoinMarketCap z 13 września 2026:
https://coinmarketcap.com/historical/20260913/

Wbudowana kolejność tickerów to:
`BTC ETH USDT BNB XRP USDC SOL TRX HYPE ZEC DOGE XMR LINK LEO ADA XLM USDE DAI BCH USD1`.

Do repozytorium nie trafiają kursy, kapitalizacje ani dane pobierane w czasie
działania. Są to wyłącznie krótkie identyfikatory używane przez lokalną regułę.
Lista może zostać zmieniona dopiero w następnym wydaniu po aktualizacji testów
i dokumentacji. Stabilne wewnętrzne nazwy kategorii `MONEY_AMOUNT_PLN_USD` i
`CRYPTO_AMOUNT_BTC_XRP` pozostają zachowane dla zgodności istniejącego stanu.
