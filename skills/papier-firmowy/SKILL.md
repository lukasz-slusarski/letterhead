---
name: papier-firmowy
description: Papier firmowy dla każdego PDF-a (umowa, oferta, raport, instrukcja dla klienta, list) w wyglądzie właściwej firmy (logo, font, kolory, dane prawne). Użyj zawsze, gdy powstaje PDF albo dokument do wydruku lub wysłania, gdy poprawiasz wygląd takiego dokumentu i gdy dodajesz nową firmę do szablonów.
---

# Papier firmowy

Treść piszesz w Markdownie, wygląd daje marka z `marki/<slug>/`. Silnik: pandoc robi HTML, Chromium (Playwright) drukuje PDF. Wszystkie komendy:

```bash
P=${CLAUDE_SKILL_DIR}/silnik/papier.py
python3 $P marki                       # jakie firmy są dostępne
python3 $P pdf dok.md --marka przyklad  # dok.pdf obok; --typ, -o wynik.pdf, --html (podgląd)
python3 $P sprawdz [marka]             # kompletność marki
```

## Kroki

1. **Firma.** Zapytaj „Dla jakiej firmy jest ten dokument?” i pokaż listę z `papier.py marki`. Pomiń pytanie tylko wtedy, gdy firma wynika wprost z rozmowy albo z projektu. Dokument dla klienta (instrukcja, raport) idzie na papierze firmy, która go przygotowała, nie klienta. Wybraną markę wpisz do frontmattera (`marka:`).
2. **Typ.** Dobierz `typ:` (tabela niżej) i napisz treść w Markdownie z elementami z sekcji „Elementy”.
3. **PDF.** `python3 $P pdf dok.md`. Gdy komenda odmawia, bo marce brakuje danych (np. NIP do umowy), zapytaj o nie, a nie obchodź tego innym typem.
4. **Sprawdzenie.** Obejrzyj każdą stronę PDF-a (Read z `pages`). Gotowe, gdy: font jest marki (`pdffonts dok.pdf` pokazuje rodzinę z `marka.yaml`), logo jest na pierwszej stronie, stopka ma logomark (od drugiej strony, gdy marka ma `logo.znak`), domenę i numer strony, u góry stron od drugiej nic, żaden nagłówek ani akapit przed zrzutem nie wisi sam na końcu strony.

## Typy dokumentu

| `typ:` | Na co | Nagłówek | Frontmatter poza `title` |
|---|---|---|---|
| `dokument` (domyślny) | oferta, raport, opis usługi, materiał dla zespołu | okładka: logo, etykieta, tytuł, data | `subtitle`, `label`, `date`, `footer` |
| `umowa` | umowy, NDA, zlecenia | logo i dane prawne firmy, tytuł na środku, stopka z NIP | `subtitle` („zawarta w … dnia …”), `podpisy: [Wykonawca, Zamawiający]` |
| `instrukcja` | instrukcje krok po kroku ze zrzutami | logo, kontakt, etykieta, tytuł | `subtitle`, `label`, `date` |
| `list` | pismo, list przewodni | logo i dane prawne, adresat, data | `do: \|` (adresat, kilka linii), `miejscowosc`, `date`, `podpis`, `rola` |

Przykłady każdego typu: `przyklady/*.md`. Próbki wszystkich typów dla marki: `python3 $P probka <marka> -o katalog`.

## Elementy

| Markdown | Wygląd |
|---|---|
| `## Sekcja` | nagłówek ze znacznikiem w kolorze akcentu (w umowie bez znacznika) |
| tabela pipe | zaokrąglona ramka, ciemny nagłówek; wiersz z `**Razem**` w pierwszej komórce podświetlony |
| `> tekst` | callout w kolorze akcentu |
| `::: {.callout .warn}` … `:::` | callout: `.warn`, `.info`, `.ok`, `.gray` |
| `::: card` … `:::` | karta; `{.card .warm}`, `{.card .dark}` |
| `::::: grid` z kartami | dwie kolumny; `{.grid .three}` trzy |
| `[300 zł]{.big}` | duża liczba lub cena w karcie |
| `[P0]{.tag .red}` | pigułka: `.red`, `.dark`, `.blue`, `.green`, `.amber`, bez klasy szara |
| `::: krok` z `[1]{.nr} tekst` i `![opis](zrzut.png)` | krok instrukcji, nie łamie się między stronami; `{width=200px}` po obrazku zmniejsza mały zrzut |
| `::: strony` z dwoma `::: {}` i `[Wykonawca]{.rola}` | blok stron umowy (dwie karty) |
| `::: page-break` `:::` | nowa strona |

Ścieżki obrazków są względne do pliku `.md`. Obrazki muszą leżeć w katalogu dokumentu (albo podkatalogu); spoza niego tylko z `--pliki KATALOG`, inne zostaną pominięte.

## Układ strony

Ten sam dla wszystkich marek i typów. Zmieniasz go w `silnik/papier.py` (`MARGINES`, `css_marki`), nie w markach.

- Odstęp treści od krawędzi kartki jest taki sam z każdej strony: 16 mm (`MARGINES` w `silnik/papier.py`).
- Pierwsza strona: u góry pełne logo; stopka: domena na środku, numer strony po prawej.
- Strony od drugiej: u góry nic; stopka: logomark po lewej, domena na środku, numer strony po prawej.
- Daty w nagłówku ani w stopce nie ma; data, jeśli potrzebna, jest w treści (okładka, umowa, list).

## Wygląd

- Kolory, font i logo zmieniasz tylko w `marki/<slug>/marka.yaml` (i ewentualnie `marki/<slug>/extra.css`). `silnik/baza.css` jest wspólny dla wszystkich marek i używa wyłącznie zmiennych.
- Wyróżnienie robi tło, nigdy jednostronny border w kolorze akcentu.
- Treść po polsku, z polskimi znakami, bez myślnika (—).

## Nowa firma

Lista rzeczy do zebrania i kroki: [KONFIGURACJA.md](KONFIGURACJA.md). Skrót: `python3 $P nowa <slug>`, uzupełnij `marka.yaml`, `python3 $P sprawdz <slug>`, obejrzyj `probka`.
