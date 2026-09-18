# S-07.01.04 — Reports and artifacts

## Problem and success criteria

A browser-agent run already produces verified findings with provenance. Today the
owner can inspect those findings in `report.html`, but sending them to somebody
else still means manually rebuilding a spreadsheet, slide deck or PDF.

This story succeeds when the same verified findings can be rendered as XLSX,
PPTX or PDF and **every claim retains the trace step that supports it**.

Leading indicator: reports produced per research run.

## Why no AI is used

Artifact generation is deterministic formatting, not reasoning. The run already
used the model where judgement was needed and then host code verified every
surviving claim. Sending those facts through a second model would add cost,
latency and a new hallucination surface.

The artifact layer therefore reads only the append-only trace. It cannot add a
claim, rewrite one or invent provenance.

## Data flow

```text
AgentRun
  -> append-only Trace
       -> verified finding
          field
          value
          kind/confidence
          source URL
          source quote
          captured_at
          source step id
               |
               v
        artifacts.claims()
          re-resolve source step
          fail closed if missing
               |
       +-------+---------+
       |       |         |
       v       v         v
     XLSX     PPTX      PDF
   openpyxl   OOXML   existing report.html
      |        |         |
 trace row   step id   Chromium print
 internal    on each    local file://
 hyperlink   claim
```

No provider, broker or model transport exists in this path.

## Formats

### XLSX

Uses the existing `openpyxl` dependency. The workbook has two sheets:

- **Findings** — one row per verified claim.
- **Trace** — the run's actual steps.

The **Trace Step** cell on every finding is an internal workbook hyperlink to
that exact row in the Trace sheet. Page-controlled strings beginning with
spreadsheet formula prefixes are forced to literal text before writing.

### PPTX

A deliberately plain 16:9 Office Open XML package, built with the standard
library. There is one title slide and one slide per verified finding. Each claim
slide includes field, value, kind/confidence, source URL, quote, capture time
and the exact trace step id.

There are no external relationships, macros, remote fonts or network assets.

### PDF

PDF reuses `agent/report.py`, which already escapes hostile page text and loads
nothing from the network. The installed Chrome/Edge/Brave/Chromium browser is
started headless against a temporary empty profile and prints that local HTML
file to PDF.

No `--no-sandbox` flag is used. Background networking, sync and component
updates are disabled for the render process.

If no supported browser exists, PDF generation fails with the next action rather
than returning a fake/empty PDF.

## Storage and privacy

Artifacts are written beside the run's own trace:

```text
<run>/
  trace.jsonl
  report.html
  report.xlsx
  report.pptx
  report.pdf
```

Where the OS supports POSIX permissions, generated files are set to `0600`
because they contain harvested values. Nothing is uploaded automatically.

## Failure controls

Artifact generation refuses to proceed when a finding names a trace step that
cannot be resolved. This re-check is deliberate even though provenance was
verified when the run completed: exported files outlive processes, and a copied
claim without its evidence should not be silently blessed again.

The spreadsheet path neutralises formula injection and invalid XML control
characters. PPTX text is XML-escaped. PDF inherits the existing report HTML's
stored-XSS controls.

## CLI

```bash
offsetx-artifacts --run-dir /path/to/run --format xlsx
offsetx-artifacts --run-dir /path/to/run --format pptx
offsetx-artifacts --run-dir /path/to/run --format pdf
offsetx-artifacts --run-dir /path/to/run --format all
```

Optional PDF browser override:

```bash
offsetx-artifacts --run-dir /path/to/run --format pdf \
  --browser /path/to/chrome
```

## Architecture trade-offs

A new PPTX/PDF dependency was rejected.

For PPTX, the required output is intentionally small: text slides and standard
package relationships. Office Open XML is already a ZIP/XML platform format, so
adding a presentation framework only to write this subset would increase the
locked dependency surface.

For PDF, hand-writing a PDF would lose reliable Unicode/font/rendering support.
The product already owns a Chromium boundary, so printing the existing safe HTML
is both smaller and more correct.

If later requirements include branded templates, charts, arbitrary slide
editing or non-browser server-side PDF generation, those change the shape enough
to justify a dedicated document library as a new decision.

## Migration and rollback

No database schema changes.

Rollback is code-only. Existing `report.html` and traces are unchanged. The
three new artifact files are derived outputs and may be deleted/rebuilt without
touching the source trace.

## Known limits

- PPTX is a clean text deck, not a PowerPoint design engine.
- PDF requires a locally installed Chromium-family browser.
- No cloud publishing or collaborative editing.
- No AI summarisation in this layer.
- Artifact generation does not repair a broken trace; it refuses it.
