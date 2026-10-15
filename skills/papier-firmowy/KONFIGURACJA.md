# Nowa marka: co trzeba zebrać

Cała marka to jeden folder `marki/<slug>/` z plikiem `marka.yaml`, logo i fontami. Kod silnika się nie zmienia.

## Kroki

1. `python3 ${CLAUDE_SKILL_DIR}/silnik/papier.py nowa <slug>` (slug: małe litery, np. `nowa-firma`). Tworzy folder z wzoru.
2. Zbierz rzeczy z listy niżej i wpisz je do `marki/<slug>/marka.yaml`.
3. `python3 ${CLAUDE_SKILL_DIR}/silnik/papier.py sprawdz <slug>`. Błędy trzeba poprawić, uwagi warto przejrzeć.
4. `python3 ${CLAUDE_SKILL_DIR}/silnik/papier.py probka <slug> -o /tmp/probka-<slug>`. Obejrzyj każdy PDF, pokaż właścicielowi marki.
5. Commit do repo, w którym trzymasz skill.

## Lista do zebrania

| Co | Skąd zwykle | Obowiązkowe | Uwagi |
|---|---|---|---|
| Nazwa wyświetlana i jedno zdanie opisu | właściciel | tak | po nazwie agent rozpoznaje markę |
| Logo na jasne tło | brand book, Figma, strona www (SVG z kodu strony) | tak | SVG; PNG tylko duży, z przezroczystym tłem |
| Logo na ciemne tło | jak wyżej | nie | |
| Logomark (skrócone logo, sam znak) | jak wyżej | nie | SVG; pokazuje się w stopce stron od drugiej (lewy dolny róg), wysokość `znak_wysokosc` (domyślnie 5mm) |
| Font (pliki) | brand book, Google Fonts, folder `fonts/` strony | tak | ttf, otf albo woff2; sprawdź licencję na osadzanie w PDF; potrzebne polskie znaki (latin-ext) |
| Kolor marki (akcent) | brand book, tokeny CSS strony | tak | sprawdź kontrast z bielą, `sprawdz` to policzy |
| Kolor tekstu i nagłówków | jak wyżej | tak | tekst ciemny, nie czysta czerń, jeśli marka ma swój |
| Kolor ciemny (nagłówki tabel, etykiety) | jak wyżej | tak | często ciemna wersja koloru marki |
| Tła: karta i ciepłe tło okładki | jak wyżej | tak | jasne, delikatne, do druku |
| Kolor przygaszony i linii | jak wyżej | tak | szary z palety marki |
| Strona www, e-mail ogólny, telefon | właściciel | www lub e-mail | e-mail firmowy, nie prywatny pracownika |
| Dane prawne: nazwa podmiotu, adres, NIP, reprezentant | KRS/CEIDG, faktury | do umów i listów | bez nich `pdf` odmówi typu umowa i list |
| Tekst stopki ofert i raportów | właściciel | nie | domyślnie nazwa marki |
| Charakter: zaokrąglenia, kropka w tytule, waga nagłówków | brand book, wygląd strony | nie | dobierz tak, żeby PDF przypominał stronę firmy |

## Gdy marka potrzebuje czegoś więcej

Jeśli różnicy nie da się ustawić w `marka.yaml`, dodaj `marki/<slug>/extra.css`. Silnik dokleja go po wspólnym CSS. Nie wpisuj kolorów marki do `silnik/baza.css`.

## Pułapki

- Font zmienny (jeden plik na wszystkie wagi) wpisz z wagą jako zakres, np. `"300 700"`. Sprawdź `pdffonts plik.pdf`, czy w PDF jest właściwa rodzina.
- Font w dwóch plikach (latin i latin-ext) wymaga pola `zakres` (unicode-range) przy każdym pliku, inaczej polskie znaki wezmą się z innego pliku.
- Logo SVG z tekstem jako `<text>` zamiast krzywych wyrenderuje się fontem systemowym. Użyj logo z krzywymi.
