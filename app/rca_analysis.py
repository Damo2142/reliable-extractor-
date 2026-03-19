"""
Reliable Controls .rca Archive Parser (RC Archive — Animation/Graphics)

Reverse-engineered format for RC-Studio animation files (.rca).
These files contain the interactive HTML5/Canvas graphics displayed on
controller screens and web interfaces (AHU diagrams, valve animations,
fan sprites, damper positions, etc.).

FILE FORMAT (completely cracked — 100% understood):
====================================================

  [4 bytes]  PNG thumbnail size (little-endian uint32)
  [N bytes]  PNG thumbnail image data (standard PNG, starts with 89 50 4E 47)
  [4 bytes]  ZIP payload size (little-endian uint32)
  [M bytes]  ZIP archive (standard PKZIP, starts with PK 50 4B 03 04)

  Total file size = 4 + png_size + 4 + zip_size

The format is a simple container: a preview thumbnail followed by a ZIP
archive containing the animation assets. No encryption, no obfuscation,
no proprietary binary encoding — unlike .pan files.

ZIP CONTENTS (varies by complexity):
  - dialog-config.json    — Animation metadata, BACnet point bindings, custom attributes
  - <AnimName>.js         — Main Dojo/dijit widget (animation logic, sprite sheet control)
  - _HtmlAnimation.js     — Base class for animations (older format, V02-V03 era)
  - sprite.png            — Sprite sheet for simple animations (single element)
  - bg.png                — Background image for complex multi-element animations
  - <component>.png       — Individual component sprites (fan.png, coil.png, etc.)

FORMAT EVOLUTION (observed across versions):
  V02-V03 (older): _HtmlAnimation.js base class included in archive
                    dialog-config.json has basic Points/Custom Attributes
  V04-V05 (newer): _HtmlAnimation.js may be omitted (loaded from RC-Studio runtime)
                    dialog-config.json gains: VersionId, Information[], EQUIPMENTview[]
                    EQUIPMENTview provides declarative layout (positions, sizes, animation types)

DIALOG-CONFIG.JSON SCHEMA:
  {
    "Name": str,                    -- Human-readable animation name
    "VersionId": str,               -- (V04+) Machine-readable ID
    "Width": int,                   -- Canvas width in pixels
    "Height": int,                  -- Canvas height in pixels
    "FixedPointCount": bool,        -- Whether point count is fixed
    "CanUseDiv": bool,              -- (V04+) Whether div-based rendering is supported
    "Custom Attributes": [          -- User-configurable parameters
      {
        "name": str,                -- Attribute group name
        "Attributes": [
          {
            "title": str,           -- Display label
            "description": str,     -- Help text
            "value": any,           -- Default value (number, bool, string)
            "type": str,            -- "number", "bool", "string"
            "variable": str         -- JavaScript variable name
          }
        ]
      }
    ],
    "Points": [                     -- BACnet point binding slots
      {
        "Purpose": str,             -- What this point controls (e.g., "Fan", "Coil")
        "Comment"/"comment": str,   -- Data type hint
        "Type": str,                -- "binary and analog", "binary and analog(0/1)", etc.
        "link": bool,               -- Whether linked to a BACnet object
        "textSize": bool            -- Whether text size is configurable
      }
    ],
    "Information": [                -- (V04+) Version notes and usage instructions
      { "Version": str, "Content": str }
    ],
    "EQUIPMENTview": [              -- (V04+) Declarative layout elements
      {
        "dimensions": { "top_left_x": int, "top_left_y": int, "width": int, "height": int },
        "type": "image" | "object",
        "include_element": str,     -- (optional) Conditional display, e.g., "var:showFilter"
        "image": { "file_path": str },                  -- For type="image"
        "object": {                                       -- For type="object"
          "display_type": "animation",
          "maximum_value": int | str,                     -- Number or "var: varName"
          "minimum_value": int | str,
          "animation": {
            "type": "loop" | "loopnstop" | "multistate",
            "first_frame": int,                           -- (optional) Starting frame
            "frame_filenames": [str]                      -- Sprite sheet filenames
          }
        }
      }
    ]
  }

COMPARISON WITH .PAN FORMAT:
  .pan: Proprietary binary, magic 0x0023BAC0, "Mu" object headers,
        property-tag encoding, big-endian BACnet ObjIDs.
        Contains BACnet programming (loops, schedules, trends, values).
  .rca: Simple container (PNG thumbnail + ZIP), standard formats throughout.
        Contains HTML5/Canvas animation graphics and BACnet point bindings.
  No structural relationship between the two formats.

Usage:
  reader = RcaReader('/path/to/file.rca')
  reader.parse()
  print(reader.config)           # dialog-config.json as dict
  reader.extract_thumbnail('thumb.png')
  reader.extract_all('/output/dir/')
  reader.dump_info()
"""

import io
import json
import os
import struct
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional


class RcaReader:
    """Parser for Reliable Controls .rca (RC Archive) animation files.

    The .rca format is:
      [uint32 LE: png_size] [PNG data] [uint32 LE: zip_size] [ZIP data]
    """

    def __init__(self, filepath: str):
        self.filepath = Path(filepath)
        self.filename = self.filepath.name
        self.data: bytes = b''
        self.png_size: int = 0
        self.png_data: bytes = b''
        self.zip_size: int = 0
        self.zip_data: bytes = b''
        self.zip_file: Optional[zipfile.ZipFile] = None
        self.config: Dict[str, Any] = {}
        self.file_list: List[str] = []
        self._parsed = False

    def parse(self) -> 'RcaReader':
        """Parse the .rca file. Returns self for chaining."""
        self.data = self.filepath.read_bytes()

        if len(self.data) < 12:
            raise ValueError(f"File too small to be a valid .rca: {len(self.data)} bytes")

        # Read PNG thumbnail size (first 4 bytes, little-endian uint32)
        self.png_size = struct.unpack_from('<I', self.data, 0)[0]

        # Validate PNG signature at offset 4
        if self.data[4:8] != b'\x89PNG':
            raise ValueError(
                f"Expected PNG signature at offset 4, got: {self.data[4:8].hex()}"
            )

        # Extract PNG data
        png_start = 4
        png_end = 4 + self.png_size
        self.png_data = self.data[png_start:png_end]

        # Validate PNG ends with IEND chunk
        if b'IEND' not in self.png_data[-12:]:
            raise ValueError("PNG data does not end with IEND chunk")

        # Read ZIP payload size (4 bytes after PNG, little-endian uint32)
        zip_size_offset = png_end
        if zip_size_offset + 4 > len(self.data):
            raise ValueError("File truncated: missing ZIP size field")

        self.zip_size = struct.unpack_from('<I', self.data, zip_size_offset)[0]

        # Extract ZIP data
        zip_start = zip_size_offset + 4
        zip_end = zip_start + self.zip_size
        self.zip_data = self.data[zip_start:zip_end]

        # Validate ZIP signature
        if self.zip_data[:2] != b'PK':
            raise ValueError(
                f"Expected PK ZIP signature at offset {zip_start}, "
                f"got: {self.zip_data[:4].hex()}"
            )

        # Validate total size
        expected_size = 4 + self.png_size + 4 + self.zip_size
        if expected_size != len(self.data):
            raise ValueError(
                f"Size mismatch: header says {expected_size}, "
                f"file is {len(self.data)} bytes"
            )

        # Open ZIP and read contents
        self.zip_file = zipfile.ZipFile(io.BytesIO(self.zip_data))
        self.file_list = [info.filename for info in self.zip_file.infolist()]

        # Parse dialog-config.json
        if 'dialog-config.json' in self.file_list:
            config_bytes = self.zip_file.read('dialog-config.json')
            self.config = json.loads(config_bytes.decode('utf-8'))

        self._parsed = True
        return self

    # ---- Extraction Methods ----

    def extract_thumbnail(self, output_path: str) -> str:
        """Extract the PNG thumbnail to a file."""
        self._ensure_parsed()
        Path(output_path).write_bytes(self.png_data)
        return output_path

    def extract_file(self, name: str, output_path: str) -> str:
        """Extract a specific file from the ZIP archive."""
        self._ensure_parsed()
        if name not in self.file_list:
            raise FileNotFoundError(f"'{name}' not found in archive. Files: {self.file_list}")
        Path(output_path).write_bytes(self.zip_file.read(name))
        return output_path

    def extract_all(self, output_dir: str) -> List[str]:
        """Extract all files (thumbnail + ZIP contents) to a directory."""
        self._ensure_parsed()
        outdir = Path(output_dir)
        outdir.mkdir(parents=True, exist_ok=True)

        extracted = []

        # Thumbnail
        thumb_path = outdir / 'thumbnail.png'
        thumb_path.write_bytes(self.png_data)
        extracted.append(str(thumb_path))

        # ZIP contents
        for name in self.file_list:
            file_path = outdir / name
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(self.zip_file.read(name))
            extracted.append(str(file_path))

        return extracted

    def read_file(self, name: str) -> bytes:
        """Read a file from the ZIP archive and return its bytes."""
        self._ensure_parsed()
        if name not in self.file_list:
            raise FileNotFoundError(f"'{name}' not found in archive. Files: {self.file_list}")
        return self.zip_file.read(name)

    def read_text(self, name: str) -> str:
        """Read a text file from the ZIP archive."""
        return self.read_file(name).decode('utf-8')

    # ---- Metadata Accessors ----

    @property
    def name(self) -> str:
        """Animation name from dialog-config.json."""
        return self.config.get('Name', self.filename)

    @property
    def version_id(self) -> Optional[str]:
        """Machine-readable version ID (V04+ only)."""
        return self.config.get('VersionId')

    @property
    def width(self) -> int:
        """Canvas width in pixels."""
        return self.config.get('Width', 0)

    @property
    def height(self) -> int:
        """Canvas height in pixels."""
        return self.config.get('Height', 0)

    @property
    def points(self) -> List[Dict]:
        """BACnet point binding definitions."""
        return self.config.get('Points', [])

    @property
    def custom_attributes(self) -> List[Dict]:
        """User-configurable attributes."""
        return self.config.get('Custom Attributes', [])

    @property
    def equipment_view(self) -> List[Dict]:
        """Declarative layout elements (V04+ only)."""
        return self.config.get('EQUIPMENTview', [])

    @property
    def information(self) -> List[Dict]:
        """Version notes and instructions (V04+ only)."""
        return self.config.get('Information', [])

    @property
    def image_files(self) -> List[str]:
        """List of image files (PNG) in the archive."""
        return [f for f in self.file_list if f.lower().endswith('.png')]

    @property
    def js_files(self) -> List[str]:
        """List of JavaScript files in the archive."""
        return [f for f in self.file_list if f.lower().endswith('.js')]

    @property
    def has_equipment_view(self) -> bool:
        """Whether this animation uses the newer EQUIPMENTview format."""
        return 'EQUIPMENTview' in self.config

    @property
    def format_version(self) -> str:
        """Detected format generation: 'v1' (older, has _HtmlAnimation.js) or 'v2' (newer)."""
        if '_HtmlAnimation.js' in self.file_list and not self.has_equipment_view:
            return 'v1'
        return 'v2'

    # ---- Display / Debug ----

    def dump_info(self) -> str:
        """Return a human-readable summary of the .rca file."""
        self._ensure_parsed()
        lines = []
        lines.append(f"=== RCA Analysis: {self.filename} ===")
        lines.append(f"  File size: {len(self.data):,} bytes")
        lines.append(f"  Thumbnail PNG: {self.png_size:,} bytes")
        lines.append(f"  ZIP payload: {self.zip_size:,} bytes")
        lines.append(f"  Format: {self.format_version}")
        lines.append(f"")
        lines.append(f"  Animation: {self.name}")
        if self.version_id:
            lines.append(f"  Version ID: {self.version_id}")
        lines.append(f"  Canvas: {self.width} x {self.height} px")
        lines.append(f"")

        lines.append(f"  BACnet Points ({len(self.points)}):")
        for i, pt in enumerate(self.points, 1):
            purpose = pt.get('Purpose', 'unknown')
            ptype = pt.get('Type', 'unknown')
            lines.append(f"    {i}. {purpose} ({ptype})")

        if self.custom_attributes:
            lines.append(f"")
            lines.append(f"  Custom Attributes:")
            for group in self.custom_attributes:
                lines.append(f"    [{group.get('name', 'unnamed')}]")
                for attr in group.get('Attributes', []):
                    title = attr.get('title', '')
                    val = attr.get('value', '')
                    var = attr.get('variable', '')
                    lines.append(f"      {title}: {val} (var: {var})")

        if self.equipment_view:
            lines.append(f"")
            lines.append(f"  Equipment View Elements ({len(self.equipment_view)}):")
            for i, elem in enumerate(self.equipment_view, 1):
                dims = elem.get('dimensions', {})
                etype = elem.get('type', '?')
                pos = f"({dims.get('top_left_x', 0)}, {dims.get('top_left_y', 0)})"
                size = f"{dims.get('width', 0)}x{dims.get('height', 0)}"
                cond = elem.get('include_element', '')
                cond_str = f" [if {cond}]" if cond else ""

                if etype == 'image':
                    img = elem.get('image', {}).get('file_path', '?')
                    lines.append(f"    {i}. IMAGE {img} at {pos} {size}{cond_str}")
                elif etype == 'object':
                    obj = elem.get('object', {})
                    anim = obj.get('animation', {})
                    atype = anim.get('type', '?')
                    frames = anim.get('frame_filenames', [])
                    lines.append(f"    {i}. OBJECT [{atype}] {frames} at {pos} {size}{cond_str}")

        lines.append(f"")
        lines.append(f"  ZIP Contents ({len(self.file_list)} files):")
        for info in self.zip_file.infolist():
            lines.append(f"    {info.filename}: {info.file_size:,} bytes")

        if self.information:
            lines.append(f"")
            lines.append(f"  Information:")
            for info in self.information:
                ver = info.get('Version', '?')
                content = info.get('Content', '')
                # Truncate long content
                preview = content[:200] + ('...' if len(content) > 200 else '')
                lines.append(f"    Version {ver}: {preview}")

        return '\n'.join(lines)

    def hex_dump(self, offset: int = 0, length: int = 256) -> str:
        """Return a hex dump of the raw file data (for debugging)."""
        result = []
        chunk = self.data[offset:offset + length]
        for i in range(0, len(chunk), 16):
            row = chunk[i:i + 16]
            hex_part = ' '.join(f'{b:02x}' for b in row)
            ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in row)
            result.append(f'{offset + i:08x}: {hex_part:<48s} {ascii_part}')
        return '\n'.join(result)

    # ---- Internal ----

    def _ensure_parsed(self):
        if not self._parsed:
            raise RuntimeError("Call parse() before accessing data")


# ---- Utility Functions ----

def scan_rca_directory(directory: str) -> List[Dict[str, Any]]:
    """Scan a directory for .rca files and return summary info for each."""
    results = []
    dirpath = Path(directory)
    for rca_file in sorted(dirpath.glob('*.rca')):
        try:
            reader = RcaReader(str(rca_file)).parse()
            results.append({
                'filename': rca_file.name,
                'file_size': len(reader.data),
                'name': reader.name,
                'version_id': reader.version_id,
                'width': reader.width,
                'height': reader.height,
                'points': len(reader.points),
                'images': len(reader.image_files),
                'format': reader.format_version,
                'has_equipment_view': reader.has_equipment_view,
                'files': reader.file_list,
            })
        except Exception as e:
            results.append({
                'filename': rca_file.name,
                'error': str(e),
            })
    return results


def extract_all_thumbnails(directory: str, output_dir: str) -> List[str]:
    """Extract thumbnails from all .rca files in a directory."""
    outdir = Path(output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    extracted = []
    for rca_file in sorted(Path(directory).glob('*.rca')):
        try:
            reader = RcaReader(str(rca_file)).parse()
            thumb_name = rca_file.stem + '_thumb.png'
            thumb_path = outdir / thumb_name
            reader.extract_thumbnail(str(thumb_path))
            extracted.append(str(thumb_path))
        except Exception as e:
            print(f"  Error extracting {rca_file.name}: {e}")
    return extracted


def compare_rca_files(path_a: str, path_b: str) -> Dict[str, Any]:
    """Compare two .rca files and report differences."""
    a = RcaReader(path_a).parse()
    b = RcaReader(path_b).parse()

    diff = {
        'file_a': a.filename,
        'file_b': b.filename,
        'thumbnail_same': a.png_data == b.png_data,
        'thumbnail_size': (a.png_size, b.png_size),
        'config_differences': {},
        'file_differences': {
            'only_in_a': [f for f in a.file_list if f not in b.file_list],
            'only_in_b': [f for f in b.file_list if f not in a.file_list],
            'size_changes': {},
            'content_changes': [],
        },
    }

    # Compare config keys
    all_keys = set(a.config.keys()) | set(b.config.keys())
    for key in sorted(all_keys):
        va = a.config.get(key)
        vb = b.config.get(key)
        if va != vb:
            diff['config_differences'][key] = {
                'a': va if not isinstance(va, (list, dict)) or len(str(va)) < 200 else f"({type(va).__name__}, len={len(va)})",
                'b': vb if not isinstance(vb, (list, dict)) or len(str(vb)) < 200 else f"({type(vb).__name__}, len={len(vb)})",
            }

    # Compare shared files
    common_files = set(a.file_list) & set(b.file_list)
    for fname in sorted(common_files):
        data_a = a.read_file(fname)
        data_b = b.read_file(fname)
        if len(data_a) != len(data_b):
            diff['file_differences']['size_changes'][fname] = (len(data_a), len(data_b))
        if data_a != data_b:
            diff['file_differences']['content_changes'].append(fname)

    return diff


# ---- CLI Main ----

if __name__ == '__main__':
    import sys

    ANIM_DIR = '/srv/dfa/shared/files/vendors/reliable/assets/_shared/Animation/'

    if len(sys.argv) > 1:
        # Analyze specific file(s)
        for path in sys.argv[1:]:
            try:
                reader = RcaReader(path).parse()
                print(reader.dump_info())
                print()
            except Exception as e:
                print(f"Error parsing {path}: {e}")
    else:
        # Analyze all .rca files in the default directory
        print("=" * 70)
        print("Reliable Controls .rca Format Analysis")
        print("=" * 70)
        print()

        rca_files = sorted(Path(ANIM_DIR).glob('*.rca'))
        if not rca_files:
            print(f"No .rca files found in {ANIM_DIR}")
            sys.exit(1)

        for rca_file in rca_files:
            try:
                reader = RcaReader(str(rca_file)).parse()
                print(reader.dump_info())
                print()
            except Exception as e:
                print(f"Error parsing {rca_file.name}: {e}")
                print()

        # Compare V03 vs V05
        v03 = os.path.join(ANIM_DIR, 'Heatpump-Ws02-Concl-Multi-V03.rca')
        v05 = os.path.join(ANIM_DIR, 'Heatpump-Ws02-Concl-Multi-V05.rca')
        if os.path.exists(v03) and os.path.exists(v05):
            print("=" * 70)
            print("Version Comparison: Heatpump V03 vs V05")
            print("=" * 70)
            diff = compare_rca_files(v03, v05)
            print(f"  Thumbnail identical: {diff['thumbnail_same']}")
            print(f"  Thumbnail sizes: {diff['thumbnail_size']}")
            print(f"  Config changes: {list(diff['config_differences'].keys())}")
            print(f"  Files only in V03: {diff['file_differences']['only_in_a']}")
            print(f"  Files only in V05: {diff['file_differences']['only_in_b']}")
            print(f"  Files with size changes: {diff['file_differences']['size_changes']}")
            print(f"  Files with content changes: {diff['file_differences']['content_changes']}")
