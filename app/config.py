from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    upload_root: Path = Path("/srv/dfa/shared/files/vendors/reliable/uploads")
    library_root: Path = Path("/srv/dfa/shared/files/vendors/reliable/library")
    assets_root: Path = Path("/srv/dfa/shared/files/vendors/reliable/assets")
    master_descriptions: Path = Path("/srv/dfa/shared/files/vendors/reliable/master_descriptions.json")
    pfg_exe: Path = Path("/srv/reliable-generator/pfg/PanelFileGenerator.exe")
    blank_xml: Path = Path("/srv/dfa/shared/files/vendors/reliable/BlankXML.xml")
    wine_bin: str = "wine"
    pfg_timeout: int = 120

    CATEGORIES: dict = None

    def __post_init__(self):
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
        for p in [self.library_root, self.assets_root]:
            p.mkdir(parents=True, exist_ok=True)
        if not self.blank_xml.exists():
            self.blank_xml.parent.mkdir(parents=True, exist_ok=True)
            self.blank_xml.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<points></points>\n')
