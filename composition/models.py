"""
SBS Composition Engine v2 — Data Models
Vendor-neutral module definitions + Reliable Controls output tool
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class PointType(str, Enum):
    AI = "AI"
    AO = "AO"
    BI = "BI"
    BO = "BO"
    AV = "AV"
    BV = "BV"
    MV = "MV"
    LOOP = "LOOP"
    TABLE = "TABLE"
    SCHEDULE = "SCHEDULE"
    TREND = "TREND"
    PROGRAM = "PROGRAM"
    SYSTEM_GROUP = "SYSTEM_GROUP"


class TrendType(str, Enum):
    POLLED = "polled"
    COV = "cov"


@dataclass
class InputPoint:
    """Physical input terminal point"""
    row: int                        # Fixed row number = terminal number
    name: str                       # Point name suffix (after {device-name}-)
    point_type: str                 # "AI" or "BI"
    range_code: str                 # RC Studio range string
    description: str
    units: str = ""
    table_ref: Optional[str] = None # Table name if range uses a scaling table
    module: str = ""                # Which module provides this point


@dataclass
class OutputPoint:
    """Physical output terminal point"""
    row: int                        # Fixed row number = terminal number
    name: str
    point_type: str                 # "AO" or "BO"
    range_code: str
    description: str
    min_v: float = 2.0              # Minimum voltage
    max_v: float = 10.0             # Maximum voltage
    reverse: bool = False           # True = reverse acting (10V→2V)
    units: str = "%"
    module: str = ""


@dataclass
class ValuePoint:
    """Software value (AV/BV/MV) — no physical terminal"""
    instance: int                   # BACnet instance number
    name: str
    point_type: str                 # "AV", "BV", or "MV"
    default: object                 # Default present value
    description: str
    units: str = ""
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    states: Optional[dict] = None   # For MV: {1: "Occ", 2: "Byp", ...}
    module: str = ""


@dataclass
class LoopDef:
    """PID loop definition"""
    instance: int
    name: str                       # e.g. "DSP-LOOP"
    input_ref: str                  # Point name for input
    setpoint_ref: str               # Point name for setpoint
    output_ref: str                 # Point name for output (optional, info only)
    p_band: float                   # Proportional band
    integral: float                 # Integral time (minutes)
    derivative: float = 0.0         # Derivative time
    action: str = "direct"          # "direct" (+) or "reverse" (-)
    bias: str = "H"                 # Bias type
    description: str = ""
    module: str = ""


@dataclass
class TableDef:
    """Scaling or lookup table"""
    instance: int
    name: str
    input_units: str
    output_units: str
    data_points: list               # List of [input, output] pairs
    description: str = ""
    module: str = ""


@dataclass
class ArrayDef:
    """BACnet array object (type 142) — sequential float slots"""
    instance: int
    name: str
    size: int                       # Number of float elements
    description: str = ""
    module: str = ""


@dataclass
class ProgramDef:
    """Control program (.bas file)"""
    instance: int
    name: str                       # e.g. "CONFIG-PRG"
    filename: str                   # e.g. "PRG01-CONFIG.bas"
    code: str                       # Full .bas source code
    enabled: bool = True
    description: str = ""
    module: str = ""
    exec_order: int = 0             # Execution order priority


@dataclass
class ScheduleDef:
    """Weekly schedule"""
    instance: int
    name: str
    default_state: str              # e.g. "Unoccupied"
    states: list                    # e.g. ["Unoccupied", "Occupied"]
    priority: int = 10
    description: str = ""
    module: str = ""


@dataclass
class TrendDef:
    """Single-point trend log (STL)"""
    instance: int
    name: str
    monitored_point: str            # Point name to trend
    trend_type: str = "polled"      # "polled" or "cov"
    interval: str = "00:15:00"      # For polled trends
    cov_delta: float = 0.2          # For COV trends
    buffer_size: int = 1334
    module: str = ""


@dataclass
class SystemGroupDef:
    """System group = graphic page in RC Studio"""
    name: str                       # e.g. "{device-name}-SYSTEM"
    description: str = ""
    module: str = ""
    conditional: bool = False       # True = only if feature selected


@dataclass
class Module:
    """A composable HVAC control module"""
    id: str                         # e.g. "htg-hw", "clg-chw", "erw"
    name: str                       # Human name
    category: str                   # "core", "cooling", "heating", etc.
    description: str

    # What this module provides
    inputs: list = field(default_factory=list)         # List of InputPoint
    outputs: list = field(default_factory=list)        # List of OutputPoint
    values: list = field(default_factory=list)         # List of ValuePoint
    loops: list = field(default_factory=list)          # List of LoopDef
    tables: list = field(default_factory=list)         # List of TableDef
    arrays: list = field(default_factory=list)         # List of ArrayDef
    programs: list = field(default_factory=list)       # List of ProgramDef
    schedules: list = field(default_factory=list)      # List of ScheduleDef
    trends: list = field(default_factory=list)         # List of TrendDef
    system_groups: list = field(default_factory=list)  # List of SystemGroupDef

    # SOO paragraph for spec documents
    soo_paragraph: str = ""

    # Dependencies
    requires: list = field(default_factory=list)       # Module IDs required
    conflicts: list = field(default_factory=list)      # Module IDs that conflict

    # Metadata
    mutually_exclusive_group: str = ""  # e.g. "cooling" — only one from this group
    is_core: bool = False               # True = always included
    is_stub_fallback: bool = False      # True = process LAST; points are skipped if
                                        # any real module already provides that name
                                        # under inputs/outputs/values. Use for shared
                                        # default-value points that real modules override.
    compatible_families: list = field(default_factory=list)  # Equipment families this module applies to
                                        # e.g. ["uv"] for UV-only, ["ahu", "rtu"] for shared
                                        # Empty list = show everywhere (shared/core modules)


@dataclass
class ControllerConfig:
    """A complete controller configuration — output of the assembler"""
    device_name: str = "{device-name}"
    parent_name: str = "{parent}"
    equipment_family: str = "AHU-VAV"

    # Selected modules
    selected_modules: list = field(default_factory=list)

    # Assembled points (merged from all modules)
    inputs: list = field(default_factory=list)
    outputs: list = field(default_factory=list)
    values: list = field(default_factory=list)
    loops: list = field(default_factory=list)
    tables: list = field(default_factory=list)
    arrays: list = field(default_factory=list)
    programs: list = field(default_factory=list)
    schedules: list = field(default_factory=list)
    trends: list = field(default_factory=list)
    system_groups: list = field(default_factory=list)

    # Controller selection result
    controller_model: str = ""
    expansion_count: int = 0
    expansion_model: str = ""
    highest_input_row: int = 0
    highest_output_row: int = 0

    # SOO assembled text
    soo_document: str = ""


@dataclass
class CustomUnit:
    """SBS standard custom unit enumeration"""
    index: int
    analog_text: str = ""
    digital_on: str = ""
    digital_off: str = ""
    multi_states: list = field(default_factory=list)  # Up to 8 states
