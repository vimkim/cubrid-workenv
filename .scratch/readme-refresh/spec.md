# README refresh

Status: resolved

## Scope

Improve the whole README, with one static, hand-authored SVG. Keep runtime code,
other documentation, installation behavior, and existing evidence unchanged.

## Project story

- Audience: CUBRID developers using several source worktrees on one Linux host.
- One-sentence value: prepare each worktree explicitly, then use native CUBRID
  commands with its selected installation and runtime resources.
- Primary proof: ticket09 coexistence evidence, with physical databases both
  named `testdb`, csql/JDBC values 111 and 222, and B healthy after A stops.
- First successful action: install the CLI, initialize a built installation,
  source the generated environment, and read 42 through csql.
- Visual theme: two independent worktree lanes with dedicated installations
  and databases; no generated artwork or animation is needed.

## Art direction

- Palette: background `#102a30`, foreground `#f1f6f3`, primary `#75d6bf`,
  accent `#e0b780`, muted `#adc1bf`.
- Typography: system sans-serif for hierarchy; system monospace for SQL values.
  The key diagram labels are 40–60 SVG units on a 1200-unit canvas.
- Shape: 12/20-unit radii, 2/3-unit strokes, generous spacing.
- Motif: one lane per worktree, never a shared installation or physical DB.
- Composition: compact technical diagram with a complete dark background.

## Content order

Value and recorded proof → install and first SQL → environment mechanism →
command reference → boundaries → verification and development links.

Keep executable commands, limits, and supporting explanations in Markdown.
Move allocation internals behind existing guide links. Clearly identify
historical native evidence rather than implying a fresh engine test.

## Provenance and validation

The SVG illustrates `tests/evidence/ticket09-coexistence/results.json` and its
native logs. The integrated report identifies CUBRID 11.5.0.2635-30043f4 and
Java 8. Neither graphic nor copy claims new platform or version coverage.

Validate image references and SVG compatibility with the beautify skill's
audit, check local links and CLI syntax, and visually inspect 900px and 360px
renders on light and dark page backgrounds. Keep temporary preview artifacts
outside the checkout. Commit only the README, SVG, and this design record.

## Result

- README reorganized around recorded coexistence proof and a first SQL query.
  Commands, recovery boundaries, and reproduction details remain searchable
  Markdown or linked existing guides.
- Image audit passed; 23 local links/anchors resolved; all five shell snippets
  parsed with Bash; documented options matched the live CLI help.
- Headless Chromium previews inspected on light/dark backgrounds at a 900px
  content width and a 360px mobile viewport. No page overflow, missing image, or
  SVG text clipping. The SVG was also rendered independently at 900px/360px
  with librsvg to check font fallback and label spacing.
- No runtime changes or new native-engine runs. Historical test evidence is
  explicitly identified as such in the README.
