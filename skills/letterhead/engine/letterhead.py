#!/usr/bin/env python3
"""Letterhead: Markdown -> PDF in a company's branding (pandoc -> HTML -> Chromium/Playwright).

  python3 letterhead.py brands                          # list brands and their status
  python3 letterhead.py pdf doc.md --brand example      # doc.pdf next to it (brand can also be in frontmatter)
  python3 letterhead.py pdf doc.md --brand example --type contract -o contract.pdf --html
  python3 letterhead.py check [BRAND]                   # is the brand complete (files, colors, contrast, legal data)
  python3 letterhead.py new SLUG                        # new brand from brands/_template
  python3 letterhead.py sample BRAND [-o DIR]           # render every file in examples/ in this brand

Document types (frontmatter `type:` or --type): document (default: proposal, report), contract, guide, letter.
"""
import base64, argparse, html, pathlib, re, shutil, subprocess, sys, tempfile, urllib.parse

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
BRANDS = ROOT / "brands"
EXAMPLES = ROOT / "examples"
BASE_CSS = ROOT / "engine" / "base.css"
TYPES = ("document", "contract", "guide", "letter")

COLORS = ("text", "headings", "accent", "on_accent", "dark", "on_dark",
          "muted", "lines", "card", "warm")
# (foreground, background, minimum WCAG contrast): checked by `check`
PAIRS = [("text", "#ffffff", 7.0), ("headings", "#ffffff", 7.0), ("muted", "#ffffff", 4.5),
         ("on_accent", "accent", 4.5), ("on_dark", "dark", 4.5), ("headings", "warm", 4.5),
         ("text", "card", 4.5), ("accent", "#ffffff", 3.0)]


# ---------- brands ----------

def list_brands():
    return sorted(p.name for p in BRANDS.iterdir() if p.is_dir() and not p.name.startswith("_")
                  and (p / "brand.yaml").exists())

def load_brand(name):
    slug = name.strip().lower()
    for s in list_brands():
        b = yaml.safe_load((BRANDS / s / "brand.yaml").read_text())
        if slug in (s, str(b.get("name", "")).lower()):
            b["_slug"], b["_dir"] = s, BRANDS / s
            return b
    sys.exit(f"No brand \"{name}\". Available: {', '.join(list_brands())}. "
             f"New brand: python3 letterhead.py new SLUG")

def lum(hexc):
    h = hexc.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)

def contrast(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)

def check_brand(b):
    """Returns (errors, warnings). An error blocks the PDF, a warning does not."""
    errors, warnings = [], []
    d = b["_dir"]
    for k in ("name", "colors", "font", "logo"):
        if not b.get(k):
            errors.append(f"missing section `{k}`")
    c = b.get("colors") or {}
    for name in COLORS:
        v = str(c.get(name, ""))
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", v):
            errors.append(f"colors.{name}: missing or wrong format (\"{v}\", expected #RRGGBB)")
    if not errors:
        for fg, bg, minimum in PAIRS:
            r = contrast(c[fg], c.get(bg, bg))
            if r < minimum:
                warnings.append(f"contrast {fg} on {bg}: {r:.2f}:1 (recommended {minimum}:1)")
    f = b.get("font") or {}
    if not f.get("family"):
        errors.append("font.family: missing")
    if not f.get("files"):
        errors.append("font.files: no font files (the PDF would fall back to a system font)")
    for p in f.get("files") or []:
        if not (d / p["file"]).exists():
            errors.append(f"font: file not found {p['file']}")
    lg = b.get("logo") or {}
    if not lg.get("file") or not (d / lg["file"]).exists():
        errors.append(f"logo.file: file not found {lg.get('file')}")
    if lg.get("light") and not (d / lg["light"]).exists():
        errors.append(f"logo.light: file not found {lg['light']}")
    if lg.get("mark") and not (d / lg["mark"]).exists():
        errors.append(f"logo.mark: file not found {lg['mark']}")
    elif lg.get("mark") and not lg["mark"].endswith(".svg"):
        errors.append("logo.mark: must be SVG")
    ent = b.get("entity") or {}
    missing = [x for x in ("name", "address", "tax_id") if not ent.get(x)]
    if missing:
        warnings.append(f"entity: missing {', '.join(missing)}; contracts and letters will be refused")
    con = b.get("contact") or {}
    if not con.get("website") and not con.get("email"):
        warnings.append("contact: no website and no e-mail")
    return errors, warnings


# ---------- HTML ----------

# Distance from the paper edge, the same on every side: the logo at the top and the footer
# at the bottom sit exactly as far from the edge as the text does on the left and right.
MARGIN = 16

def uri(p):
    return pathlib.Path(p).resolve().as_uri()

def css_string(t):
    """Text as a CSS string. Escapes < and > too, so frontmatter cannot close the <style> tag."""
    return '"' + "".join(c if c.isalnum() or c in " .,:;@/-_()" else f"\\{ord(c):x} " for c in str(t)) + '"'

def brand_css(b, meta):
    c, f, s, d = b["colors"], b["font"], b.get("style") or {}, b["_dir"]
    faces = []
    for p in f["files"]:
        rng = f"unicode-range: {p['range']};" if p.get("range") else ""
        faces.append(f"@font-face {{ font-family: '{f['family']}'; src: url('{uri(d / p['file'])}'); "
                     f"font-weight: {p.get('weight', 400)}; font-style: {p.get('style', 'normal')}; {rng} }}")
    variables = "\n".join(f"  --c-{n.replace('_', '-')}: {c[n]};" for n in COLORS)
    box = (f"font-family: '{f['family']}', sans-serif; font-size: 7.5pt; color: {c['muted']}; "
           f"vertical-align: bottom; padding-bottom: {MARGIN}mm;")
    return "\n".join(faces) + f"""
:root {{
{variables}
  --font: '{f['family']}', sans-serif;
  --w-headings: {f.get('heading_weight', 700)};
  --tracking-headings: {f.get('heading_tracking', '0')};
  --font-settings: {f.get('settings') or 'normal'};
  --r-md: {s.get('radius', '12px')};
  --r-lg: {s.get('radius_large', '18px')};
  --logo-h: {b['logo'].get('height', '24px')};
}}
@page {{
  size: A4; margin: {MARGIN}mm {MARGIN}mm {MARGIN + 10}mm {MARGIN}mm;
  @bottom-center {{ content: {css_string(footer(b, meta))}; {box} text-align: center; }}
  @bottom-right {{ content: counter(page) " / " counter(pages); {box} text-align: right; }}
}}
{logomark(b)}
@page :first {{ @bottom-left {{ content: none; }} }}
"""

def logomark(b):
    """Logomark in the bottom-left corner from page two on (logo.mark in brand.yaml)."""
    lg = b["logo"]
    if not lg.get("mark"):
        return ""
    svg = (b["_dir"] / lg["mark"]).read_text()
    vb = [float(x) for x in re.search(r'viewBox="([^"]+)"', svg).group(1).split()]
    h = float(str(lg.get("mark_height", "5mm")).removesuffix("mm")) * 96 / 25.4
    w = h * vb[2] / vb[3]
    svg = re.sub(r'<svg[^>]*?\swidth="[^"]*"', lambda x: x.group(0).rsplit(" width=", 1)[0] + f' width="{w:.1f}"', svg, count=1)
    svg = re.sub(r'(<svg[^>]*?\s)height="[^"]*"', lambda x: x.group(1) + f'height="{h:.1f}"', svg, count=1)
    if ' width="' not in svg.split(">", 1)[0]:
        svg = svg.replace("<svg", f'<svg width="{w:.1f}" height="{h:.1f}"', 1)
    data = "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
    return f"@page {{ @bottom-left {{ content: url('{data}'); vertical-align: bottom; padding-bottom: {MARGIN}mm; }} }}"

def footer(b, meta):
    """Footer centre: the domain. Every page has logomark, domain and page number at the bottom; nothing at the top."""
    return str(meta.get("footer") or b.get("footer") or (b.get("contact") or {}).get("website") or b["name"])

def logo_img(b):
    return f'<img class="logo" src="{uri(b["_dir"] / b["logo"]["file"])}" alt="{html.escape(b["name"])}">'

def sender(b, with_entity=True):
    ent, con = b.get("entity") or {}, b.get("contact") or {}
    lines = []
    if with_entity and ent.get("name"):
        lines += [f"<b>{html.escape(ent['name'])}</b>", html.escape(ent.get("address", ""))]
        if ent.get("tax_id"):
            lines.append(f"{html.escape(str(ent.get('tax_label', 'Tax ID')))} {html.escape(str(ent['tax_id']))}")
    contact = [con.get(x) for x in ("website", "email", "phone") if con.get(x)]
    if contact:
        lines.append(html.escape(", ".join(contact)))
    return '<div class="sender">' + "<br>".join(l for l in lines if l) + "</div>"

def header(meta, b, kind):
    e = lambda k: html.escape(str(meta.get(k, "")))
    ml = lambda k: html.escape(str(meta.get(k, ""))).strip().replace("\n", "<br>")
    label = f'<div class="label">{e("label")}</div>' if meta.get("label") else ""
    if kind == "document":
        if not meta.get("title"):
            return ""
        dot = '<span class="dot">.</span>' if (b.get("style") or {}).get("title_dot") else ""
        return f"""<div class="cover">{logo_img(b)}{label}
  <h1>{e("title")}{dot}</h1>
  {f'<p class="subtitle">{e("subtitle")}</p>' if meta.get("subtitle") else ''}
  {f'<div class="meta">{e("date")}</div>' if meta.get("date") else ''}</div>"""
    head = f'<div class="head">{logo_img(b)}{sender(b, kind != "guide")}</div>'
    if kind == "contract":
        return head + f"""<div class="title-block"><h1>{e("title")}</h1>
  {f'<div class="meta">{e("subtitle")}</div>' if meta.get("subtitle") else ''}</div>"""
    if kind == "guide":
        return head + f"""<div class="title-block">{label}<h1>{e("title")}</h1>
  {f'<p class="subtitle">{e("subtitle")}</p>' if meta.get("subtitle") else ''}</div>"""
    if kind == "letter":
        when = ", ".join(x for x in (str(meta.get("place", "")), str(meta.get("date", ""))) if x)
        subject = f'<p class="subject">{e("title")}</p>' if meta.get("title") else ""
        return head + f"""<div class="recipient"><div class="to">{ml("to")}</div>
  <div class="date">{html.escape(when)}</div></div>{subject}"""
    return ""

def closing(meta, b, kind):
    e = lambda k: html.escape(str(meta.get(k, "")))
    if kind == "contract" and meta.get("signatures"):
        cols = "".join(f"<div><p>{html.escape(str(p))}</p></div>" for p in meta["signatures"])
        return f'<div class="signatures">{cols}</div>'
    if kind == "letter" and meta.get("signature"):
        return f"""<div class="letter-signature"><p class="name">{e("signature")}</p>
  {f'<p class="role">{e("role")}</p>' if meta.get("role") else ''}</div>"""
    return ""

def frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}, text
    return yaml.safe_load(m.group(1)) or {}, text[m.end():]

def build_html(src, b, kind, meta, body):
    if meta.get("title") and kind != "letter":
        body = re.sub(r"\A\s*# [^\n]*\n", "", body, count=1)
    # pandoc needs a blank line before a list; without it the list merges into the paragraph
    body = re.sub(r"(?m)^([^\n\-\d|>\s:][^\n]*)\n(?=(- |\d+\. ))", r"\1\n\n", body)
    frag = subprocess.run(
        ["pandoc", "-f", "markdown+pipe_tables+fenced_divs+bracketed_spans+smart-implicit_figures-raw_html-raw_attribute", "-t", "html5"],
        input=body, capture_output=True, text=True, check=True).stdout
    marker = (b.get("style") or {}).get("heading_marker", "dot")
    css = brand_css(b, meta) + BASE_CSS.read_text()
    extra = b["_dir"] / "extra.css"
    if extra.exists():
        css += "\n" + extra.read_text()
    return f"""<!doctype html><html lang="{html.escape(str(meta.get('lang', 'en')))}"><head><meta charset="utf-8">
<base href="{uri(src.parent)}/"><title>{html.escape(str(meta.get('title', '')))}</title>
<style>{css}</style></head>
<body class="type-{kind} marker-{marker} brand-{b['_slug']}">
{header(meta, b, kind)}{frag}{closing(meta, b, kind)}</body></html>"""

def allowed(url, dirs):
    """May the browser load this URL: data:, or a file inside the document, skill or --files directories."""
    if url.startswith("data:"):
        return True
    if not url.startswith("file:"):
        return False
    # Unusual URLs are rejected instead of interpreted, so Python and Chromium cannot read them differently:
    # non-local host, query, backslash, encoded slash or NUL, a . or .. segment.
    u = urllib.parse.urlsplit(url)
    if u.netloc not in ("", "localhost") or u.query or "\\" in u.path:
        return False
    if any(z in u.path.lower() for z in ("%2f", "%5c", "%00")):
        return False
    raw = urllib.parse.unquote(u.path)
    if any(s in (".", "..") for s in raw.split("/")):
        return False
    path = pathlib.Path(raw).resolve()
    return any(path.is_relative_to(k) for k in dirs)

def render(doc, out, dirs=()):
    from playwright.sync_api import sync_playwright
    with tempfile.TemporaryDirectory() as tmp:
        dirs = [pathlib.Path(k).resolve() for k in (*dirs, ROOT, tmp)]
        page = pathlib.Path(tmp) / "doc.html"
        page.write_text(doc)
        with sync_playwright() as p:
            br = p.chromium.launch()
            # Document content cannot run scripts or reach the network: local files and data: only.
            ctx = br.new_context(java_script_enabled=False)
            # Images only from the document directory (and below), the skill, or --files.
            ctx.route("**/*", lambda r: r.continue_() if allowed(r.request.url, dirs) else r.abort())
            pg = ctx.new_page()
            pg.goto(page.as_uri())
            pg.wait_for_load_state("networkidle")
            pg.evaluate("document.fonts.ready")
            pg.pdf(path=str(out), print_background=True, prefer_css_page_size=True)
            br.close()

def make_pdf(src, brand=None, kind=None, out=None, keep_html=False, files=()):
    src = pathlib.Path(src).resolve()
    meta, body = frontmatter(src.read_text())
    brand = brand or meta.get("brand")
    if not brand:
        sys.exit(f"Which company is this for? Pass --brand or `brand:` in frontmatter. "
                 f"Available: {', '.join(list_brands())}")
    b = load_brand(brand)
    errors, _ = check_brand(b)
    if errors:
        sys.exit(f"Brand {b['_slug']} is incomplete:\n  " + "\n  ".join(errors))
    kind = kind or meta.get("type", "document")
    if kind not in TYPES:
        sys.exit(f"Unknown type \"{kind}\". Available: {', '.join(TYPES)}")
    ent = b.get("entity") or {}
    if kind in ("contract", "letter") and not (ent.get("name") and ent.get("tax_id")):
        sys.exit(f"Type {kind} needs the legal data of brand {b['_slug']} (entity.name, address, tax_id in brand.yaml).")
    out = pathlib.Path(out).resolve() if out else src.with_suffix(".pdf")
    doc = build_html(src, b, kind, meta, body)
    if keep_html:
        out.with_suffix(".html").write_text(doc)
    render(doc, out, [src.parent, *files])
    return out


# ---------- commands ----------

def cmd_brands(_):
    for s in list_brands():
        b = load_brand(s)
        errors, warnings = check_brand(b)
        state = "ERRORS" if errors else ("warnings" if warnings else "ok")
        print(f"{s:12} {b['name']:20} [{state}]  {b.get('description', '')}")

def cmd_check(a):
    code = 0
    for s in ([a.brand] if a.brand else list_brands()):
        b = load_brand(s)
        errors, warnings = check_brand(b)
        print(f"== {b['_slug']} ({b['name']}): {'OK' if not errors else 'INCOMPLETE'}")
        for e in errors:
            print(f"  ERROR   {e}")
        for w in warnings:
            print(f"  warning {w}")
        code |= bool(errors)
    return code

def cmd_new(a):
    slug = a.slug.lower()
    if not re.fullmatch(r"[a-z0-9-]+", slug):
        sys.exit("Slug: lowercase letters, digits and hyphens, e.g. acme-studio")
    target = BRANDS / slug
    if target.exists():
        sys.exit(f"Brand {slug} already exists: {target}")
    shutil.copytree(BRANDS / "_template", target)
    print(f"Created {target}\nFill in brand.yaml following BRANDS.md, add logo and fonts, "
          f"then: python3 letterhead.py check {slug}")

def cmd_pdf(a):
    print(make_pdf(a.file, a.brand, a.type, a.out, a.html, a.files or ()))

def cmd_sample(a):
    b = load_brand(a.brand)
    target = pathlib.Path(a.out or ".").resolve()
    target.mkdir(parents=True, exist_ok=True)
    ent = b.get("entity") or {}
    for p in sorted(EXAMPLES.glob("*.md")):
        meta, _ = frontmatter(p.read_text())
        if meta.get("type") in ("contract", "letter") and not ent.get("tax_id"):
            print(f"skipping {p.name}: brand {b['_slug']} has no legal data")
            continue
        print(make_pdf(p, b["_slug"], out=target / f"{b['_slug']}-{p.stem}.pdf"))

def main():
    ap = argparse.ArgumentParser(description="Letterhead: branded PDFs from Markdown")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("brands").set_defaults(f=cmd_brands)
    s = sub.add_parser("check"); s.add_argument("brand", nargs="?"); s.set_defaults(f=cmd_check)
    s = sub.add_parser("new"); s.add_argument("slug"); s.set_defaults(f=cmd_new)
    s = sub.add_parser("pdf"); s.add_argument("file"); s.add_argument("--brand"); s.add_argument("--type", choices=TYPES)
    s.add_argument("-o", "--out"); s.add_argument("--html", action="store_true")
    s.add_argument("--files", action="append", metavar="DIR",
                   help="extra directory with images outside the document directory (repeatable)")
    s.set_defaults(f=cmd_pdf)
    s = sub.add_parser("sample"); s.add_argument("brand"); s.add_argument("-o", "--out"); s.set_defaults(f=cmd_sample)
    a = ap.parse_args()
    return a.f(a) or 0

if __name__ == "__main__":
    sys.exit(main())
