#!/usr/bin/env python3
"""Papier firmowy: Markdown -> PDF w wyglądzie wybranej marki (pandoc -> HTML -> Chromium/Playwright).

  python3 papier.py marki                          # lista marek i ich stan
  python3 papier.py pdf dok.md --marka przyklad     # dok.pdf obok (marka może też być we frontmatterze)
  python3 papier.py pdf dok.md --marka przyklad --typ umowa -o umowa.pdf --html
  python3 papier.py sprawdz [MARKA]                 # czy marka jest kompletna (pliki, kolory, kontrast, dane prawne)
  python3 papier.py nowa SLUG                       # nowa marka z wzoru marki/_wzor
  python3 papier.py probka MARKA [-o KATALOG]       # wszystkie przykłady z przyklady/ w danej marce

Typy dokumentu (frontmatter `typ:` albo --typ): dokument (domyślny: oferta, raport, opis), umowa, instrukcja, list.
"""
import base64, argparse, html, pathlib, re, shutil, subprocess, sys, tempfile, urllib.parse

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
MARKI = ROOT / "marki"
PRZYKLADY = ROOT / "przyklady"
BAZA_CSS = ROOT / "silnik" / "baza.css"
TYPY = ("dokument", "umowa", "instrukcja", "list")

KOLORY = ("tekst", "naglowki", "akcent", "na_akcencie", "ciemny", "na_ciemnym",
          "przygaszony", "linie", "karta", "cieply")
# pary (tekst, tło, minimalny kontrast WCAG): sprawdzane przez `sprawdz`
PARY = [("tekst", "#ffffff", 7.0), ("naglowki", "#ffffff", 7.0), ("przygaszony", "#ffffff", 4.5),
        ("na_akcencie", "akcent", 4.5), ("na_ciemnym", "ciemny", 4.5), ("naglowki", "cieply", 4.5),
        ("tekst", "karta", 4.5), ("akcent", "#ffffff", 3.0)]


# ---------- marki ----------

def lista_marek():
    return sorted(p.name for p in MARKI.iterdir() if p.is_dir() and not p.name.startswith("_")
                  and (p / "marka.yaml").exists())

def wczytaj_marke(nazwa):
    slug = nazwa.strip().lower()
    for s in lista_marek():
        m = yaml.safe_load((MARKI / s / "marka.yaml").read_text())
        if slug in (s, str(m.get("nazwa", "")).lower()):
            m["_slug"], m["_dir"] = s, MARKI / s
            return m
    sys.exit(f"Nie ma marki „{nazwa}”. Dostępne: {', '.join(lista_marek())}. "
             f"Nowa marka: python3 papier.py nowa SLUG")

def lum(hexc):
    h = hexc.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)

def kontrast(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)

def sprawdz_marke(m):
    """Zwraca (błędy, ostrzeżenia). Błąd blokuje PDF, ostrzeżenie nie."""
    bledy, uwagi = [], []
    d = m["_dir"]
    for k in ("nazwa", "kolory", "font", "logo"):
        if not m.get(k):
            bledy.append(f"brak sekcji `{k}`")
    k = m.get("kolory") or {}
    for c in KOLORY:
        v = str(k.get(c, ""))
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", v):
            bledy.append(f"kolory.{c}: brak albo zły format („{v}”, potrzebny #RRGGBB)")
    if not bledy:
        for fg, bg, minimum in PARY:
            a, b = k[fg], k.get(bg, bg)
            r = kontrast(a, b)
            if r < minimum:
                uwagi.append(f"kontrast {fg} na {bg}: {r:.2f}:1 (zalecane {minimum}:1)")
    f = m.get("font") or {}
    if not f.get("rodzina"):
        bledy.append("font.rodzina: brak")
    if not f.get("pliki"):
        bledy.append("font.pliki: brak plików fontu (PDF dostałby font systemowy)")
    for p in f.get("pliki") or []:
        if not (d / p["plik"]).exists():
            bledy.append(f"font: nie ma pliku {p['plik']}")
    lg = m.get("logo") or {}
    if not lg.get("plik") or not (d / lg["plik"]).exists():
        bledy.append(f"logo.plik: nie ma pliku {lg.get('plik')}")
    if lg.get("jasne") and not (d / lg["jasne"]).exists():
        bledy.append(f"logo.jasne: nie ma pliku {lg['jasne']}")
    if lg.get("znak") and not (m["_dir"] / lg["znak"]).exists():
        bledy.append(f"logo.znak: nie ma pliku {lg['znak']}")
    elif lg.get("znak") and not lg["znak"].endswith(".svg"):
        bledy.append("logo.znak: musi być SVG")
    pod = m.get("podmiot") or {}
    brak = [x for x in ("nazwa", "adres", "nip") if not pod.get(x)]
    if brak:
        uwagi.append(f"podmiot: brak {', '.join(brak)}; umowy i listy nie powstaną")
    kon = m.get("kontakt") or {}
    if not kon.get("www") and not kon.get("email"):
        uwagi.append("kontakt: brak www i e-maila")
    return bledy, uwagi


# ---------- HTML ----------

# Odstęp treści od krawędzi kartki, taki sam z każdej strony: logo (lub logomark) u góry
# i stopka u dołu stoją dokładnie tyle od krawędzi, co tekst po bokach.
MARGINES = 16

def uri(p):
    return pathlib.Path(p).resolve().as_uri()

def css_tekst(t):
    """Tekst jako napis CSS. Escapuje też < i >, żeby treść z frontmattera nie zamknęła <style>."""
    return '"' + "".join(c if c.isalnum() or c in " .,:;@/-_()" else f"\\{ord(c):x} " for c in str(t)) + '"'

def css_marki(m, typ, meta):
    k, f, s, d = m["kolory"], m["font"], m.get("styl") or {}, m["_dir"]
    faces = []
    for p in f["pliki"]:
        zakres = f"unicode-range: {p['zakres']};" if p.get("zakres") else ""
        faces.append(f"@font-face {{ font-family: '{f['rodzina']}'; src: url('{uri(d / p['plik'])}'); "
                     f"font-weight: {p.get('waga', 400)}; font-style: {p.get('styl', 'normal')}; {zakres} }}")
    zmienne = "\n".join(f"  --k-{c.replace('_', '-')}: {k[c]};" for c in KOLORY)
    q = css_tekst
    box = (f"font-family: '{f['rodzina']}', sans-serif; font-size: 7.5pt; color: {k['przygaszony']}; "
           f"vertical-align: bottom; padding-bottom: {MARGINES}mm;")
    return "\n".join(faces) + f"""
:root {{
{zmienne}
  --font: '{f['rodzina']}', sans-serif;
  --w-naglowki: {f.get('waga_naglowkow', 700)};
  --tracking-naglowki: {f.get('odstep_naglowkow', '0')};
  --font-ustawienia: {f.get('ustawienia') or 'normal'};
  --r-md: {s.get('zaokraglenie', '12px')};
  --r-lg: {s.get('zaokraglenie_duze', '18px')};
  --logo-h: {m['logo'].get('wysokosc', '24px')};
}}
@page {{
  size: A4; margin: {MARGINES}mm {MARGINES}mm {MARGINES + 10}mm {MARGINES}mm;
  @bottom-center {{ content: {q(stopka(m, meta))}; {box} text-align: center; }}
  @bottom-right {{ content: counter(page) " / " counter(pages); {box} text-align: right; }}
}}
{znak_marki(m)}
@page :first {{ @bottom-left {{ content: none; }} }}
"""

def znak_mm(m):
    """Wysokość logomarku w mm, 0 gdy marka go nie ma."""
    lg = m["logo"]
    return float(str(lg.get("znak_wysokosc", "5mm")).removesuffix("mm")) if lg.get("znak") else 0

def znak_marki(m):
    """Logomark w lewym dolnym rogu stron od drugiej (logo.znak w marka.yaml)."""
    lg = m["logo"]
    if not lg.get("znak"):
        return ""
    svg = (m["_dir"] / lg["znak"]).read_text()
    vb = [float(x) for x in re.search(r'viewBox="([^"]+)"', svg).group(1).split()]
    h = znak_mm(m) * 96 / 25.4
    w = h * vb[2] / vb[3]
    svg = re.sub(r'<svg[^>]*?\swidth="[^"]*"', lambda x: x.group(0).rsplit(" width=", 1)[0] + f' width="{w:.1f}"', svg, count=1)
    svg = re.sub(r'(<svg[^>]*?\s)height="[^"]*"', lambda x: x.group(1) + f'height="{h:.1f}"', svg, count=1)
    dane = "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
    return f"@page {{ @bottom-left {{ content: url('{dane}'); vertical-align: bottom; padding-bottom: {MARGINES}mm; }} }}"

def stopka(m, meta):
    """Środek stopki: domena. Na dole każdej strony: logomark, domena, numer strony; u góry nic."""
    return str(meta.get("footer") or m.get("stopka") or (m.get("kontakt") or {}).get("www") or m["nazwa"])

def logo_img(m):
    return f'<img class="logo" src="{uri(m["_dir"] / m["logo"]["plik"])}" alt="{html.escape(m["nazwa"])}">'

def nadawca(m, z_podmiotem=True):
    pod, kon = m.get("podmiot") or {}, m.get("kontakt") or {}
    linie = []
    if z_podmiotem and pod.get("nazwa"):
        linie += [f"<b>{html.escape(pod['nazwa'])}</b>", html.escape(pod.get("adres", ""))]
        if pod.get("nip"):
            linie.append(f"NIP {html.escape(str(pod['nip']))}")
    kontakt = [kon.get(x) for x in ("www", "email", "telefon") if kon.get(x)]
    if kontakt:
        linie.append(html.escape(", ".join(kontakt)))
    return '<div class="nadawca">' + "<br>".join(l for l in linie if l) + "</div>"

def naglowek(meta, m, typ):
    e = lambda k: html.escape(str(meta.get(k, "")))
    ml = lambda k: html.escape(str(meta.get(k, ""))).strip().replace("\n", "<br>")
    label = f'<div class="label">{e("label")}</div>' if meta.get("label") else ""
    if typ == "dokument":
        if not meta.get("title"):
            return ""
        kropka = '<span class="dot">.</span>' if (m.get("styl") or {}).get("kropka_w_tytule") else ""
        return f"""<div class="cover">{logo_img(m)}{label}
  <h1>{e("title")}{kropka}</h1>
  {f'<p class="subtitle">{e("subtitle")}</p>' if meta.get("subtitle") else ''}
  {f'<div class="meta">{e("date")}</div>' if meta.get("date") else ''}</div>"""
    head = f'<div class="head">{logo_img(m)}{nadawca(m, typ != "instrukcja")}</div>'
    if typ == "umowa":
        return head + f"""<div class="tytul"><h1>{e("title")}</h1>
  {f'<div class="meta">{e("subtitle")}</div>' if meta.get("subtitle") else ''}</div>"""
    if typ == "instrukcja":
        return head + f"""<div class="tytul">{label}<h1>{e("title")}</h1>
  {f'<p class="subtitle">{e("subtitle")}</p>' if meta.get("subtitle") else ''}</div>"""
    if typ == "list":
        data = ", ".join(x for x in (str(meta.get("miejscowosc", "")), str(meta.get("date", ""))) if x)
        temat = f'<p class="temat">{e("title")}</p>' if meta.get("title") else ""
        return head + f"""<div class="adresat"><div class="do">{ml("do")}</div>
  <div class="data">{html.escape(data)}</div></div>{temat}"""
    return ""

def stopka_tresci(meta, m, typ):
    e = lambda k: html.escape(str(meta.get(k, "")))
    if typ == "umowa" and meta.get("podpisy"):
        kol = "".join(f"<div><p>{html.escape(str(p))}</p></div>" for p in meta["podpisy"])
        return f'<div class="podpisy">{kol}</div>'
    if typ == "list" and meta.get("podpis"):
        return f"""<div class="podpis-listu"><p class="imie">{e("podpis")}</p>
  {f'<p class="rola-osoby">{e("rola")}</p>' if meta.get("rola") else ''}</div>"""
    return ""

def frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}, text
    return yaml.safe_load(m.group(1)) or {}, text[m.end():]

def zbuduj_html(src, m, typ, meta, body):
    if meta.get("title") and typ != "list":
        body = re.sub(r"\A\s*# [^\n]*\n", "", body, count=1)
    # pandoc wymaga pustej linii przed listą; bez niej listy zlewają się z akapitem
    body = re.sub(r"(?m)^([^\n\-\d|>\s:][^\n]*)\n(?=(- |\d+\. ))", r"\1\n\n", body)
    frag = subprocess.run(
        ["pandoc", "-f", "markdown+pipe_tables+fenced_divs+bracketed_spans+smart-implicit_figures-raw_html-raw_attribute", "-t", "html5"],
        input=body, capture_output=True, text=True, check=True).stdout
    znacznik = (m.get("styl") or {}).get("znacznik_naglowka", "kropka")
    css = css_marki(m, typ, meta) + BAZA_CSS.read_text()
    extra = m["_dir"] / "extra.css"
    if extra.exists():
        css += "\n" + extra.read_text()
    return f"""<!doctype html><html lang="{html.escape(str(meta.get('lang', 'pl')))}"><head><meta charset="utf-8">
<base href="{uri(src.parent)}/"><title>{html.escape(str(meta.get('title', '')))}</title>
<style>{css}</style></head>
<body class="typ-{typ} znacznik-{znacznik} marka-{m['_slug']}">
{naglowek(meta, m, typ)}{frag}{stopka_tresci(meta, m, typ)}</body></html>"""

def dozwolony(url, katalogi):
    """Czy przeglądarka może wczytać ten adres: data: albo plik z katalogu dokumentu, skilla lub --pliki."""
    if url.startswith("data:"):
        return True
    if not url.startswith("file:"):
        return False
    # Adres nietypowy odrzucamy zamiast go tłumaczyć, żeby Python i Chromium nie odczytały go różnie:
    # host inny niż lokalny, zapytanie, ukośnik wsteczny, zakodowany ukośnik lub NUL, segment . albo ..
    u = urllib.parse.urlsplit(url)
    if u.netloc not in ("", "localhost") or u.query or "\\" in u.path:
        return False
    if any(z in u.path.lower() for z in ("%2f", "%5c", "%00")):
        return False
    surowa = urllib.parse.unquote(u.path)
    if any(s in (".", "..") for s in surowa.split("/")):
        return False
    sciezka = pathlib.Path(surowa).resolve()
    return any(sciezka.is_relative_to(k) for k in katalogi)

def drukuj(doc, out, katalogi=()):
    from playwright.sync_api import sync_playwright
    with tempfile.TemporaryDirectory() as tmp:
        katalogi = [pathlib.Path(k).resolve() for k in (*katalogi, ROOT, tmp)]
        page = pathlib.Path(tmp) / "doc.html"
        page.write_text(doc)
        with sync_playwright() as p:
            b = p.chromium.launch()
            # Treść dokumentu nie może uruchamiać skryptów ani sięgać do sieci: tylko pliki lokalne i data:.
            ctx = b.new_context(java_script_enabled=False)
            # Obrazki tylko z katalogu dokumentu (i podkatalogów), skilla albo wskazanych w --pliki.
            ctx.route("**/*", lambda r: r.continue_() if dozwolony(r.request.url, katalogi) else r.abort())
            pg = ctx.new_page()
            pg.goto(page.as_uri())
            pg.wait_for_load_state("networkidle")
            pg.evaluate("document.fonts.ready")
            pg.pdf(path=str(out), print_background=True, prefer_css_page_size=True)
            b.close()

def zrob_pdf(src, marka=None, typ=None, out=None, zostaw_html=False, pliki=()):
    src = pathlib.Path(src).resolve()
    meta, body = frontmatter(src.read_text())
    marka = marka or meta.get("marka")
    if not marka:
        sys.exit(f"Dla jakiej firmy? Podaj --marka albo `marka:` we frontmatterze. "
                 f"Dostępne: {', '.join(lista_marek())}")
    m = wczytaj_marke(marka)
    bledy, uwagi = sprawdz_marke(m)
    if bledy:
        sys.exit(f"Marka {m['_slug']} jest niekompletna:\n  " + "\n  ".join(bledy))
    typ = typ or meta.get("typ", "dokument")
    if typ not in TYPY:
        sys.exit(f"Nieznany typ „{typ}”. Dostępne: {', '.join(TYPY)}")
    pod = m.get("podmiot") or {}
    if typ in ("umowa", "list") and not (pod.get("nazwa") and pod.get("nip")):
        sys.exit(f"Typ {typ} wymaga danych prawnych marki {m['_slug']} (podmiot.nazwa, adres, nip w marka.yaml).")
    out = pathlib.Path(out).resolve() if out else src.with_suffix(".pdf")
    doc = zbuduj_html(src, m, typ, meta, body)
    if zostaw_html:
        out.with_suffix(".html").write_text(doc)
    drukuj(doc, out, [src.parent, *pliki])
    return out


# ---------- komendy ----------

def cmd_marki(_):
    for s in lista_marek():
        m = wczytaj_marke(s)
        bledy, uwagi = sprawdz_marke(m)
        stan = "BŁĘDY" if bledy else ("uwagi" if uwagi else "ok")
        print(f"{s:12} {m['nazwa']:20} [{stan}]  {m.get('opis', '')}")

def cmd_sprawdz(a):
    kod = 0
    for s in ([a.marka] if a.marka else lista_marek()):
        m = wczytaj_marke(s)
        bledy, uwagi = sprawdz_marke(m)
        print(f"== {m['_slug']} ({m['nazwa']}): {'OK' if not bledy else 'NIEKOMPLETNA'}")
        for b in bledy:
            print(f"  BŁĄD  {b}")
        for u in uwagi:
            print(f"  uwaga {u}")
        kod |= bool(bledy)
    return kod

def cmd_nowa(a):
    slug = a.slug.lower()
    if not re.fullmatch(r"[a-z0-9-]+", slug):
        sys.exit("Slug: małe litery, cyfry, myślnik ASCII, np. nowa-firma")
    cel = MARKI / slug
    if cel.exists():
        sys.exit(f"Marka {slug} już istnieje: {cel}")
    shutil.copytree(MARKI / "_wzor", cel)
    print(f"Utworzono {cel}\nUzupełnij marka.yaml według KONFIGURACJA.md, wrzuć logo i fonty, "
          f"potem: python3 papier.py sprawdz {slug}")

def cmd_pdf(a):
    print(zrob_pdf(a.plik, a.marka, a.typ, a.out, a.html, a.pliki or ()))

def cmd_probka(a):
    m = wczytaj_marke(a.marka)
    cel = pathlib.Path(a.out or ".").resolve()
    cel.mkdir(parents=True, exist_ok=True)
    pod = m.get("podmiot") or {}
    for p in sorted(PRZYKLADY.glob("*.md")):
        meta, _ = frontmatter(p.read_text())
        if meta.get("typ") in ("umowa", "list") and not pod.get("nip"):
            print(f"pomijam {p.name}: marka {m['_slug']} nie ma danych prawnych")
            continue
        print(zrob_pdf(p, m["_slug"], out=cel / f"{m['_slug']}-{p.stem}.pdf"))

def main():
    ap = argparse.ArgumentParser(description="Papier firmowy: PDF w wyglądzie marki")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("marki").set_defaults(f=cmd_marki)
    s = sub.add_parser("sprawdz"); s.add_argument("marka", nargs="?"); s.set_defaults(f=cmd_sprawdz)
    s = sub.add_parser("nowa"); s.add_argument("slug"); s.set_defaults(f=cmd_nowa)
    s = sub.add_parser("pdf"); s.add_argument("plik"); s.add_argument("--marka"); s.add_argument("--typ", choices=TYPY)
    s.add_argument("-o", "--out"); s.add_argument("--html", action="store_true")
    s.add_argument("--pliki", action="append", metavar="KATALOG",
                   help="dodatkowy katalog z obrazkami spoza katalogu dokumentu (można powtórzyć)")
    s.set_defaults(f=cmd_pdf)
    s = sub.add_parser("probka"); s.add_argument("marka"); s.add_argument("-o", "--out"); s.set_defaults(f=cmd_probka)
    a = ap.parse_args()
    return a.f(a) or 0

if __name__ == "__main__":
    sys.exit(main())
