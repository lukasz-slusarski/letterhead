---
name: letterhead
description: Branded letterhead for every PDF (contract, proposal, report, client guide, letter) in the right company's look (logo, font, colors, legal details). Use whenever a PDF or a document to print or send is created, when improving how such a document looks, and when adding a new company to the templates.
---

# Letterhead

You write the content in Markdown; the brand in `brands/<slug>/` gives the look. Engine: pandoc builds HTML, Chromium (Playwright) prints the PDF. All commands:

```bash
L=${CLAUDE_SKILL_DIR}/engine/letterhead.py
python3 $L brands                        # which companies are available
python3 $L pdf doc.md --brand example    # doc.pdf next to it; --type, -o out.pdf, --html (preview)
python3 $L check [brand]                 # is the brand complete
```

## Steps

1. **Company.** Ask "Which company is this document for?" and show the list from `letterhead.py brands`. Skip the question only when the company follows directly from the conversation or the project. A document for a client (guide, report) goes on the letterhead of the company that prepared it, not the client's. Put the chosen brand in the frontmatter (`brand:`).
2. **Type.** Pick `type:` (table below) and write the content in Markdown using the elements from "Elements".
3. **PDF.** `python3 $L pdf doc.md`. When the command refuses because the brand lacks data (e.g. a tax ID for a contract), ask for it instead of working around it with another type.
4. **Check.** Look at every page of the PDF. Done when: the font is the brand's (`pdffonts doc.pdf` shows the family from `brand.yaml`), the logo is on page one, the footer has the logomark (from page two, when the brand has `logo.mark`), the domain and the page number, nothing sits at the top of pages two and on, and no heading or paragraph before a screenshot is left alone at the bottom of a page.

## Document types

| `type:` | For | Header | Frontmatter besides `title` |
|---|---|---|---|
| `document` (default) | proposal, report, service description, internal material | cover: logo, label, title, date | `subtitle`, `label`, `date`, `footer` |
| `contract` | contracts, NDAs, orders | logo and company legal details, centered title, signature lines | `subtitle` ("made on …"), `signatures: [Provider, Client]` |
| `guide` | step-by-step guides with screenshots | logo, contact, label, title | `subtitle`, `label`, `date` |
| `letter` | letter, cover letter | logo and legal details, recipient, date | `to: \|` (recipient, several lines), `place`, `date`, `signature`, `role` |

Examples of every type: `examples/*.md`. Samples of all types for a brand: `python3 $L sample <brand> -o dir`.

## Elements

| Markdown | Looks like |
|---|---|
| `## Section` | heading with an accent-colored marker (no marker in contracts) |
| pipe table | rounded frame, dark header; a row with `**Total**` in the first cell is highlighted |
| `> text` | accent callout |
| `::: {.callout .warn}` … `:::` | callout: `.warn`, `.info`, `.ok`, `.gray` |
| `::: card` … `:::` | card; `{.card .warm}`, `{.card .dark}` |
| `::::: grid` with cards | two columns; `{.grid .three}` three |
| `[$300]{.big}` | big number or price in a card |
| `[P0]{.tag .red}` | pill: `.red`, `.dark`, `.blue`, `.green`, `.amber`, gray without a class |
| `::: step` with `[1]{.num} text` and `![alt](shot.png)` | guide step, never split across pages; `{width=200px}` after an image shrinks a small screenshot |
| `::: parties` with two `::: {}` and `[Provider]{.party-role}` | contract parties block (two cards) |
| `::: page-break` `:::` | new page |

Image paths are relative to the `.md` file. Images are read only from the document's directory and below; for images elsewhere pass `--files DIR`.

## Page layout

The same for every brand and type. Change it in `engine/letterhead.py` (`MARGIN`, `brand_css`), not in brands.

- The distance from the paper edge is the same on every side: 16 mm.
- Page one: full logo at the top; footer: domain in the center, page number on the right.
- Pages two and on: nothing at the top; footer: logomark on the left, domain in the center, page number on the right.
- No date in the header or footer; a date, when needed, goes in the content (cover, contract, letter).

## Look

- Colors, font and logo change only in `brands/<slug>/brand.yaml` (and optionally `brands/<slug>/extra.css`). `engine/base.css` is shared by all brands and uses variables only.
- Emphasis uses a background, never a one-sided accent border.

## Security

The document is treated as untrusted input: raw HTML is disabled in pandoc, JavaScript is off in the browser, network requests are blocked, and files load only from the document directory, the skill and `--files` directories.

## New company

What to collect and the steps: [BRANDS.md](BRANDS.md). Short version: `python3 $L new <slug>`, fill in `brand.yaml`, `python3 $L check <slug>`, look at `sample`.
