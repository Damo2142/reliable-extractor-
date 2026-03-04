"""
Read _Data.xlsx spreadsheets that define what each variant code means.
Returns dict keyed by variant ID.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def read_data_xlsx(xlsx_path: Path) -> dict:
    """
    Parse a category _Data.xlsx file.
    Expected columns (flexible): ID/Code, Description, Tags, Notes, ...
    Returns dict: { variant_id: { description, tags, notes, extra } }
    """
    try:
        import openpyxl
    except ImportError:
        logger.warning("openpyxl not installed — skipping XLSX metadata")
        return {}

    try:
        wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    except Exception as e:
        logger.warning(f"Cannot open {xlsx_path.name}: {e}")
        return {}

    result = {}
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return {}

    # Find header row (first non-empty row)
    header = None
    data_start = 0
    for i, row in enumerate(rows):
        cleaned = [str(c).strip().lower() if c else "" for c in row]
        if any(cleaned):
            header = cleaned
            data_start = i + 1
            break

    if not header:
        return {}

    # Map column names to indices — flexible matching
    def col_idx(*names):
        for name in names:
            for i, h in enumerate(header):
                if name in h:
                    return i
        return None

    id_col = col_idx("id", "code", "variant", "file")
    desc_col = col_idx("description", "desc", "name")
    tags_col = col_idx("tag", "type", "control")
    notes_col = col_idx("note", "comment", "remark")

    for row in rows[data_start:]:
        if id_col is None or id_col >= len(row):
            continue
        vid = row[id_col]
        if not vid:
            continue
        vid = str(vid).strip()

        result[vid] = {
            "description": str(row[desc_col]).strip() if desc_col is not None and desc_col < len(row) and row[desc_col] else "",
            "tags": [t.strip() for t in str(row[tags_col]).split(",") if t.strip()] if tags_col is not None and tags_col < len(row) and row[tags_col] else [],
            "notes": str(row[notes_col]).strip() if notes_col is not None and notes_col < len(row) and row[notes_col] else "",
        }

    return result
