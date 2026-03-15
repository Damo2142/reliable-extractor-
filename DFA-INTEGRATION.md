# DFA Integration — Composer API

The Composer API runs at `http://localhost:8086` (dev) from `/srv/reliable-generator-dev/`.
It provides a mix-and-match controller builder for Reliable Controls.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/composer/programs` | All 797 programs indexed with dependencies |
| POST | `/api/composer/compose` | Compose controller from selected programs |
| GET | `/api/composer/blanks` | List 46 blank controller model templates |
| POST | `/api/composer/generate-pan` | Generate .pan file (runs PFG) |
| POST | `/api/composer/generate-panx` | Generate .panx file (.pan + meta + graphics) |
| POST | `/api/composer/save` | Save a composition |
| GET | `/api/composer/compositions` | List saved compositions |
| GET | `/api/composer/compositions/{name}` | Load a saved composition |
| DELETE | `/api/composer/compositions/{name}` | Delete a saved composition |

## Compose Request

```json
{
  "selections": ["AHU-IS1DOMM:1", "RTU-IS11107:3"],
  "device_name": "AHU-01",
  "device_id": "900"
}
```

- Format is `variant:program_instance`
- Dependencies auto-resolve (all referenced points, loops, schedules, etc. are pulled in)
- Instance numbers are remapped sequentially to avoid conflicts

## Generate .panx Request

```json
{
  "composition": { "/* result from /compose */" },
  "blank_model": "MACH-Pro1-48",
  "device_name": "AHU-01",
  "device_id": "900"
}
```

Returns a downloadable .panx file (ZIP containing .pan + meta.json + graphics).

## Generate .pan Request

Same body as .panx. Returns a raw .pan file.

## Library Structure

- Location: `/srv/dfa/shared/files/vendors/reliable/library-dev/`
- 9 categories: AHU, RTU, VAV, FCU, HP, BLR, CT, MISC, CENTRAL
- 797 programs total across all variants
- Each variant is a JSON file (e.g., `VAV/VAV-IS10001.json`)

## Program Index Format

Each program from `/api/composer/programs` looks like:

```json
{
  "source_category": "AHU",
  "source_variant": "AHU-IS1DOMM",
  "program_instance": "1",
  "program_name": "{device-name}-CFG-PRG",
  "program_description": "",
  "code_preview": "10 REM ***** CONFIGURATION ...",
  "code_lines": 25,
  "dependencies": {
    "AV": [11, 12, 13, 41, 42, 43]
  },
  "dependency_details": {
    "AV": [
      {"type": "AV", "instance": "11", "name": "{device-name}-STPT", "description": "..."}
    ]
  }
}
```

## Template Format

- All point/program names use `{device-name}` placeholder
- Replaced with actual controller name at compose time
- Example: `{device-name}-STPT` becomes `AHU-01-STPT`

## Blank Panel Templates

- Location: `/srv/dfa/shared/files/vendors/reliable/blanks/`
- 46 controller models (MACH-Pro1-*, RC-FLEXair-*, RC-FLEXone-*)
- Each is a .panx ZIP with an empty .pan file for that hardware model
- Selected based on I/O requirements of the composed controller

## Key Files

| File | Description |
|------|-------------|
| `app/composer.py` | Core composer logic (~850 lines) |
| `app/main.py` | FastAPI routes |
| `generator.py` | JSON → PFG XML generation |
| `app/config.py` | Paths and category mappings |
| `static/index.html` | Full UI |

## DFA Integration Goal

When a user selects equipment type + features in DFA, auto-select the right programs
from the library and compose a controller. The flow:

1. DFA determines equipment type and required features
2. DFA calls `/api/composer/programs` to get available programs (or uses cached index)
3. DFA selects programs matching the equipment/features
4. DFA calls `/api/composer/compose` with selections + device name/ID
5. DFA calls `/api/composer/generate-panx` with the composition + appropriate blank model
6. Result is a ready-to-deploy .panx controller file

## Object Types in Compositions

The composer pulls all object types from source variants:

- **PFG-compatible** (included in .pan generation): AI, AO, AV, BI, BO, BV, MO, MV, PROGRAM, LOOP, SCHEDULE, CALENDAR
- **Excluded from PFG** (crash PFG, handled separately): DEVICE, TREND, SMARTSENSOR, SYSTEMGROUP
- **Metadata** (packaged in .panx): graphics, animations, meta.json, tables, arrays, features, hard point config
