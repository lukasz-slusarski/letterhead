# New brand: what to collect

A brand is one folder `brands/<slug>/` with `brand.yaml`, the logo and the fonts. The engine code does not change.

## Steps

1. `python3 ${CLAUDE_SKILL_DIR}/engine/letterhead.py new <slug>` (slug: lowercase, e.g. `acme-studio`). Creates the folder from the template.
2. Collect the items from the list below and enter them in `brands/<slug>/brand.yaml`.
3. `python3 ${CLAUDE_SKILL_DIR}/engine/letterhead.py check <slug>`. Errors must be fixed, warnings are worth reviewing.
4. `python3 ${CLAUDE_SKILL_DIR}/engine/letterhead.py sample <slug> -o /tmp/sample-<slug>`. Look at every PDF and show them to the brand owner.
5. Commit to the repository where you keep the skill.

## Checklist

| What | Usually from | Required | Notes |
|---|---|---|---|
| Display name and one-sentence description | owner | yes | the agent recognizes the brand by its name |
| Logo for light backgrounds | brand book, Figma, website (SVG from the site code) | yes | SVG; PNG only if large, with a transparent background |
| Logo for dark backgrounds | as above | no | |
| Logomark (short logo, the symbol only) | as above | no | SVG; shown in the footer from page two (bottom-left), height `mark_height` (default 5mm) |
| Font files | brand book, Google Fonts, the website's `fonts/` folder | yes | ttf, otf or woff2; check the license allows PDF embedding; make sure it covers the characters of your language |
| Brand color (accent) | brand book, website CSS tokens | yes | `check` computes contrast with white |
| Text and heading colors | as above | yes | dark text, not pure black if the brand has its own |
| Dark color (table headers, labels) | as above | yes | often a dark version of the brand color |
| Backgrounds: card and warm cover background | as above | yes | light and subtle, print-friendly |
| Muted and line colors | as above | yes | a gray from the brand palette |
| Website, general e-mail, phone | owner | website or e-mail | a company address, not an employee's personal one |
| Legal details: entity name, address, tax ID, representative | company register, invoices | for contracts and letters | without them `pdf` refuses the contract and letter types; `tax_label` sets the label (VAT, EIN, NIP…) |
| Footer text for proposals and reports | owner | no | defaults to the website |
| Character: corner radius, title dot, heading weight | brand book, website | no | aim for a PDF that feels like the company's website |

## When a brand needs more

If a difference cannot be set in `brand.yaml`, add `brands/<slug>/extra.css`. The engine appends it after the shared CSS. Do not put brand colors in `engine/base.css`.

## Pitfalls

- A variable font (one file for all weights) takes the weight as a range, e.g. `"300 700"`. Check `pdffonts file.pdf` for the right family in the PDF.
- A font split into two files (latin and latin-ext) needs a `range` field (unicode-range) on each file, otherwise accented characters come from the wrong file.
- An SVG logo with text as `<text>` instead of outlines renders in a system font. Use a logo with outlined text.
