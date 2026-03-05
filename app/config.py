from dataclasses import dataclass
from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class Config:
    upload_root: Path = Path("/srv/dfa/shared/files/vendors/reliable/uploads")
    library_root: Path = Path("/srv/dfa/shared/files/vendors/reliable/library")
    assets_root: Path = Path("/srv/dfa/shared/files/vendors/reliable/assets")
    master_descriptions: Path = Path("/srv/dfa/shared/files/vendors/reliable/master_descriptions.json")
    custom_categories_file: Path = Path("/srv/dfa/shared/files/vendors/reliable/custom_categories.json")
    pfg_exe: Path = Path("/srv/reliable-generator/pfg/PanelFileGenerator.exe")
    blank_xml: Path = Path("/srv/dfa/shared/files/vendors/reliable/BlankXML.xml")
    wine_bin: str = "wine"
    pfg_timeout: int = 120

    CATEGORIES: dict = None

    def __post_init__(self):
        # Built-in categories
        self.CATEGORIES = {
            "RC VAV Programming": "VAV",
            "RC RTU Programming": "RTU",
            "RC FCU Programming": "FCU",
            "RC AHU Programming": "AHU",
            "RC G36AHU Programming": "G36AHU",
            "RC G36VAV Programming": "G36VAV",
            "RC UH Programming": "UH",
            "RC VVT Programming": "VVT",
            "RC WSHP Programming": "WSHP",
        }
        # Load custom categories
        if self.custom_categories_file.exists():
            try:
                custom = json.loads(self.custom_categories_file.read_text())
                self.CATEGORIES.update(custom)
                logger.info(f"Loaded {len(custom)} custom categories")
            except Exception as e:
                logger.warning(f"Failed to load custom categories: {e}")

        for p in [self.library_root, self.assets_root]:
            p.mkdir(parents=True, exist_ok=True)
        if not self.blank_xml.exists():
            self.blank_xml.parent.mkdir(parents=True, exist_ok=True)
            self.blank_xml.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<points></points>\n')

    def save_custom_categories(self, custom: dict):
        """Save custom category mappings to JSON."""
        self.custom_categories_file.parent.mkdir(parents=True, exist_ok=True)
        self.custom_categories_file.write_text(json.dumps(custom, indent=2))
        self.CATEGORIES.update(custom)
