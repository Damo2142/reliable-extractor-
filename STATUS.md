# RC Extractor — Project Status

**Last Updated:** 2025-03-04 (Session 6)
**Repo:** git@github.com:Damo2142/reliable-extractor-.git
**Service:** rc-extractor (systemd), port 8085
**Server:** /srv/reliable-generator/

---

## What This Is

Web-based extraction tool that reads Reliable Controls .panx/.pan programming files, runs them through PFG (PanelFileGenerator.exe under Wine), parses the sidecar XML output, and stores structured JSON in a library. Part of the DFA Platform ecosystem for BAS project lifecycle automation.

**Owner:** Dave Smith, SBS Controls at Ameresco
**Related:** DFA Platform at /srv/dfa/ (separate repo: Damo2142/dfa-platform)

---

## Architecture

```
/srv/reliable-generator/          ← project root (also PFG working directory)
├── server.py                     ← uvicorn entry point
├── app/
│   ├── __init__.py
│   ├── config.py                 ← paths, category mappings, custom categories
│   ├── extractor.py              ← core engine: unzip, PFG, XML parse, library
│   ├── main.py                   ← FastAPI routes and background jobs
│   ├── parser.py                 ← DEAD CODE (not imported, extractor.py has its own parser)
│   └── xlsx_reader.py            ← reads _Data.xlsx metadata files
├── static/
│   └── index.html                ← single-file UI (vanilla JS, no framework)
├── pfg/
│   └── PanelFileGenerator.exe    ← Reliable Controls tool (runs under Wine)
├── templates/                    ← PFG template files
├── venv/                         ← Python virtual environment
├── wineprefix/                   ← Wine configuration
├── Drops/                        ← file drop zone for deploying updates
└── .gitignore
```

### External Paths

```
/srv/dfa/shared/files/vendors/reliable/
├── uploads/                      ← source .panx/.pan files organized by category folder
│   ├── RC VAV Programming/       ← 32 variants
│   ├── RC RTU Programming/       ← 34 variants
│   ├── RC FCU Programming/       ← 11 variants (loose .pan + .bas files)
│   ├── RC AHU Programming/       ← 2 variants
│   ├── RC G36AHU Programming/    ← 1 variant
│   ├── RC G36VAV Programming/    ← 3 variants
│   ├── RC UH Programming/        ← 3 variants
│   ├── RC VVT Programming/       ← 4 variants
│   └── RC WSHP Programming/      ← 12 variants
├── library/                      ← extracted JSON per variant (output)
│   ├── VAV/
│   ├── RTU/
│   └── ...
├── assets/                       ← graphics extracted from .panx files
├── master_descriptions.json      ← 117 variant ID → description mappings from Master_List.xlsx
├── custom_categories.json        ← user-added category folder mappings (if any)
└── BlankXML.xml                  ← minimal XML for PFG extraction mode
```

---

## What's Working

- [x] Variant discovery — scans upload folders, finds .panx and .pan files, reads _Data.xlsx metadata
- [x] .panx unzip — extracts .pan, meta.json, graphics assets
- [x] PFG execution — Wine + Popen with kill pattern, handles PFG hang after completion
- [x] **FIX: PFG output location** — XML written to PFG's CWD (/srv/reliable-generator/), NOT output dir. Uses snapshot+diff to find new XMLs.
- [x] **FIX: "log enabled" attribute** — PFG writes invalid `log enabled="true"` in XML. Cleaned to `logenabled="true"` before parsing.
- [x] **FIX: Control-BASIC code escaping** — `<` and `>` in `<code>` blocks escaped before XML parse, unescaped after extraction
- [x] **FIX: Bare `&` characters** — regex escapes unescaped ampersands
- [x] **FIX: Encoding** — tries UTF-8, falls back to latin-1
- [x] Regex fallback parser — if XML still fails, extracts points via regex. Saves debug copies to library/_debug/
- [x] File lock for concurrent PFG safety (fcntl)
- [x] Full object extraction: AI/AO/AV/BI/BO/BV/MO/MV/PROGRAM/LOOP/TREND/SCHEDULE/CALENDAR/TABLE/ARRAY/DEVICE/SMARTSENSOR/SYSTEMGROUP
- [x] Library JSON storage per variant
- [x] Dashboard with object count matrix per category
- [x] Variant detail view with tabbed sections
- [x] Side-by-side comparison view
- [x] Checkbox selection in sidebar for batch processing
- [x] Single variant processing
- [x] SSE progress streaming
- [x] Master descriptions from Master_List.xlsx (93 variants with full titles)
- [x] Git repo initialized and pushed to GitHub
- [x] systemd service running as user dave

---

## What's Pending (Not Yet Deployed)

These 3 files are built but NOT yet copied from Drops/:

1. **config.py** — adds custom_categories.json support
2. **main.py** — adds `/api/settings/categories` endpoints, `/api/process/selected` endpoint, `/api/library/{cat}/{vid}/save` endpoint
3. **index.html** — adds Settings panel for custom categories, editing (point names, code, trend toggles), description column in dashboard, description tooltips in sidebar

**Deploy command:**
```bash
cp /srv/reliable-generator/Drops/config.py /srv/reliable-generator/app/config.py
cp /srv/reliable-generator/Drops/main.py /srv/reliable-generator/app/main.py
cp /srv/reliable-generator/Drops/index.html /srv/reliable-generator/static/index.html
sudo systemctl restart rc-extractor
```

---

## Known Issues

1. **parser.py is dead code** — main.py imports from app.extractor, not app.parser. Can delete parser.py.
2. **VAV-IS10001 has no description** — blank in Master_List.xlsx row 25. Several other variants also missing descriptions.
3. **Binary/Multistate units show range codes** (e.g., "240") not human-readable state text. Would need a range-code-to-states lookup table from RC Studio documentation.
4. **Variant ID suffix mismatch** — some upload filenames have E suffix (e.g., RTU-ISA11110E.pan) that may not match Master_List entries (RTU-ISA11110). Currently handled by also storing stripped-E keys in master_descriptions.json.
5. **PFG error dialog under Wine** — PFG shows "Conversion failed" dialog. Under Wine with headless mode, the kill pattern handles this, but some variants may fail if the error prevents XML generation.
6. **Stale XMLs in PFG dir** — must `rm -f /srv/reliable-generator/*.xml /srv/reliable-generator/*.json` before reprocessing to avoid snapshot confusion.

---

## Key Technical Decisions

- **PFG sidecar XML, not .pan binary** — PFG exports all BACnet objects as XML when given a blank changes file. This is the only way to read .pan contents without reverse-engineering the binary format.
- **XML filename = BACnet device instance ID** — not the input filename. e.g., device 5001 → 5001.xml
- **Single-file HTML UI** — no build step, no framework. Vanilla JS with IBM Plex fonts.
- **extractor.py is the monolith** — contains engine, PFG runner, XML parser, regex fallback, library I/O. Could be split later but works fine now.
- **File lock serializes PFG** — only one PFG instance at a time since they share the CWD for output.

---

## Files Summary

| File | Lines | What It Does |
|------|-------|-------------|
| server.py | 5 | Uvicorn entry point |
| app/config.py | ~55 | Paths, category mappings, custom categories JSON |
| app/extractor.py | ~710 | Core engine: discover, unzip, PFG, parse XML, regex fallback, library |
| app/main.py | ~195 | FastAPI routes: variants, process, library, settings, save |
| app/parser.py | 176 | DEAD CODE — not used |
| app/xlsx_reader.py | 77 | Reads _Data.xlsx variant metadata |
| static/index.html | ~700 | Full UI: dashboard, detail, compare, process, settings |

---

## Tomorrow's Plan

1. Deploy the 3 pending files from Drops/
2. Verify processing completed successfully — check library/ folder for JSON files, check assets/ for graphics
3. Test the Settings panel — add a custom category, drop a .panx in it, process
4. Test editing — rename a point, edit program code, toggle a trend, save
5. Build range-code lookup table for binary/multistate state text
6. Clean up parser.py (dead code)
7. Consider: auto-process on file upload via filesystem watcher
8. Consider: DFA integration — nav link to extraction tool, API queries from DFA Field Ops module

---

## Proven PFG Command Reference

```bash
cd /srv/reliable-generator
wine pfg/PanelFileGenerator.exe \
  -i "Z:\\path\\to\\input.pan" \
  -o "Z:\\path\\to\\output.pan" \
  -c "Z:\\path\\to\\BlankXML.xml" \
  -f "Z:\\path\\to\\log.txt"
```

- Must cd to /srv/reliable-generator/ first
- Wine Z:\\ paths with backslashes
- WINEDEBUG=-all to suppress noise
- PFG writes sidecar XML to CWD, named by BACnet device instance ID
- Wine may hang — use Popen + poll + kill pattern
