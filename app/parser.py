"""
PanXML Parser
Parses the sidecar XML produced by PanelFileGenerator.
Extracts all BACnet object types and their properties.
"""

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional


class PanXMLParser:

    POINT_TYPES = {"AI", "AO", "AV", "BI", "BO", "BV", "MO", "MV"}

    @classmethod
    def parse(cls, xml_path: Path) -> dict:
        """Parse PFG sidecar XML into structured dict."""
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
        except ET.ParseError as e:
            raise ValueError(f"Malformed XML in {xml_path.name}: {e}")

        result = {
            "AI": [], "AO": [], "AV": [],
            "BI": [], "BO": [], "BV": [],
            "MO": [], "MV": [],
            "PROGRAM": [],
            "LOOP": [],
            "TREND": [],
            "SCHEDULE": [],
            "CALENDAR": [],
            "TABLE": [],
            "ARRAY": [],
            "SMARTSENSOR": [],
            "SYSTEMGROUP": [],
            "OTHER": [],
        }

        for elem in root.iter():
            tag = elem.tag.upper()

            if tag in cls.POINT_TYPES:
                result[tag].append(cls._parse_point(elem, tag))

            elif tag == "PROGRAM":
                result["PROGRAM"].append(cls._parse_program(elem))

            elif tag == "LOOP":
                result["LOOP"].append(cls._parse_loop(elem))

            elif tag in ("TREND", "TRENDLOG"):
                result["TREND"].append(cls._parse_trend(elem))

            elif tag == "SCHEDULE":
                result["SCHEDULE"].append(cls._parse_generic(elem, "SCHEDULE"))

            elif tag == "CALENDAR":
                result["CALENDAR"].append(cls._parse_generic(elem, "CALENDAR"))

            elif tag in ("TABLE", "DATATABLE"):
                result["TABLE"].append(cls._parse_generic(elem, "TABLE"))

            elif tag == "ARRAY":
                result["ARRAY"].append(cls._parse_generic(elem, "ARRAY"))

            elif tag == "SMARTSENSOR":
                result["SMARTSENSOR"].append(cls._parse_generic(elem, "SMARTSENSOR"))

            elif tag == "SYSTEMGROUP":
                result["SYSTEMGROUP"].append(cls._parse_generic(elem, "SYSTEMGROUP"))

        # Remove empty lists for cleanliness... keep keys for consistency
        return result

    # ─── Parsers per type ─────────────────────────────────────────────────────

    @classmethod
    def _parse_point(cls, elem: ET.Element, ptype: str) -> dict:
        p = cls._attrs(elem)
        return {
            "type": ptype,
            "instance": cls._get(p, "instance", "id", "objectid"),
            "name": cls._get(p, "name", "description", "objectname"),
            "unit": cls._get(p, "unit", "units", "engineeringunits"),
            "range_min": cls._get(p, "rangemin", "min", "minpresval"),
            "range_max": cls._get(p, "rangemax", "max", "maxpresval"),
            "cov": cls._get(p, "cov", "covincrement"),
            "states": cls._get_states(elem),
            "raw": p,
        }

    @classmethod
    def _parse_program(cls, elem: ET.Element) -> dict:
        p = cls._attrs(elem)
        # Code may be in a child element or CDATA
        code = ""
        for child in elem:
            if child.tag.upper() in ("CODE", "SOURCE", "BASICCODE", "PROGRAMCODE"):
                code = (child.text or "").strip()
                break
        if not code:
            code = (elem.text or "").strip()
        return {
            "instance": cls._get(p, "instance", "id"),
            "name": cls._get(p, "name", "description"),
            "code": code,
            "raw": p,
        }

    @classmethod
    def _parse_loop(cls, elem: ET.Element) -> dict:
        p = cls._attrs(elem)
        return {
            "instance": cls._get(p, "instance", "id"),
            "name": cls._get(p, "name", "description"),
            "input": cls._get(p, "input", "manipulatedvariable"),
            "output": cls._get(p, "output", "controlledvariable"),
            "setpoint": cls._get(p, "setpoint", "setpointreference"),
            "kp": cls._get(p, "kp", "proportionalgain", "gain"),
            "ti": cls._get(p, "ti", "integraltime", "integralconstant"),
            "td": cls._get(p, "td", "derivativetime", "derivativeconstant"),
            "action": cls._get(p, "action", "controlaction"),
            "raw": p,
        }

    @classmethod
    def _parse_trend(cls, elem: ET.Element) -> dict:
        p = cls._attrs(elem)
        logs = []
        for child in elem:
            logs.append(cls._attrs(child))
        return {
            "instance": cls._get(p, "instance", "id"),
            "name": cls._get(p, "name", "description"),
            "log_interval": cls._get(p, "loginterval", "interval"),
            "start_time": cls._get(p, "starttime"),
            "stop_time": cls._get(p, "stoptime"),
            "buffer_size": cls._get(p, "buffersize"),
            "references": [cls._get(cls._attrs(c), "objectref", "reference") for c in elem],
            "raw": p,
        }

    @classmethod
    def _parse_generic(cls, elem: ET.Element, tag: str) -> dict:
        p = cls._attrs(elem)
        return {
            "type": tag,
            "instance": cls._get(p, "instance", "id"),
            "name": cls._get(p, "name", "description"),
            "raw": p,
        }

    # ─── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _attrs(elem: ET.Element) -> dict:
        """Lower-case all attribute keys."""
        return {k.lower(): v for k, v in elem.attrib.items()}

    @staticmethod
    def _get(d: dict, *keys) -> Optional[str]:
        for k in keys:
            if k in d:
                return d[k]
        return None

    @staticmethod
    def _get_states(elem: ET.Element) -> list:
        states = []
        for child in elem:
            if child.tag.upper() in ("STATE", "STATETEXT", "STATES"):
                states.append(child.text or child.attrib.get("name", ""))
        return states
