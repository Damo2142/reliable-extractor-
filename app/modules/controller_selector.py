"""
SBS Controls — Controller Selector

Given I/O requirements (analog inputs, analog outputs, digital inputs, digital
outputs), selects the smallest Reliable Controls controller that fits, with
family preference based on equipment type.

Reliable Controls I/O Architecture:
    UI  = Universal Input  (can be AI or DI, jumper-selectable)
    UIO = Universal I/O    (can be AO or DI/DO, jumper-selectable)
    BO  = Binary Output    (relay, DO only)
    AO  = Dedicated Analog Output (some models)
    BI  = Dedicated Binary Input (some models like MPA series)

Selection Logic:
    1. Calculate total UI needed = num_AI + num_DI (both use universal inputs)
    2. Calculate total UO needed = num_AO (universal outputs handle analog)
    3. Calculate total BO needed = num_DO (binary outputs for relays)
    4. For MPA series: BI and BO are separate dedicated terminals
    5. Pick smallest controller in preferred family that fits
    6. If no single controller fits, flag expansion modules needed
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class ControllerModel:
    """Reliable Controls controller hardware definition."""
    id: str
    name: str
    family: str
    # Available I/O counts
    ui: int = 0       # Universal Inputs (AI or DI)
    uo: int = 0       # Universal Outputs (AO or DO)
    ao: int = 0       # Dedicated Analog Outputs
    bi: int = 0       # Dedicated Binary Inputs
    bo: int = 0       # Dedicated Binary Outputs (relays)
    # Expansion
    max_expansion: int = 0
    expansion_ui_per: int = 12   # UI per expansion module (MPP-IO)
    expansion_uo_per: int = 8    # UO per expansion module (MPP-IO)
    # Metadata
    use_case: str = ""


# ── Controller Database ──────────────────────────────────────────────────────
# Ordered smallest to largest within each family

CONTROLLERS: List[ControllerModel] = [
    # RC-FLEXair family — VAV / Terminal units
    ControllerModel(
        id="RCFA-M-12", name="RC-FLEXair M-12", family="rcfa",
        ui=1, uo=0, bo=2,
        use_case="Tiny terminal, single sensor + 2 relay outputs",
    ),
    ControllerModel(
        id="RCFA-M-33", name="RC-FLEXair M-33", family="rcfa",
        ui=3, uo=0, bo=3,
        use_case="Basic VAV/FCU, 3 sensors + 3 relay outputs",
    ),
    ControllerModel(
        id="RCFA-M-34", name="RC-FLEXair M-34", family="rcfa",
        ui=3, uo=1, bo=3,
        use_case="VAV with reheat, 3 sensors + 1 analog + 3 relay",
    ),
    ControllerModel(
        id="RCFA-M-35", name="RC-FLEXair M-35", family="rcfa",
        ui=3, uo=2, bo=3,
        use_case="Small AHU or complex VAV, 3 sensors + 2 analog + 3 relay",
    ),
    ControllerModel(
        id="RCFA-M-36", name="RC-FLEXair M-36", family="rcfa",
        ui=3, uo=3, bo=3,
        use_case="Medium terminal/small AHU, 3 sensors + 3 analog + 3 relay",
    ),

    # MACH-ProZone family — Zone controllers
    ControllerModel(
        id="MPZ-44", name="MACH-ProZone 44", family="mpz",
        ui=4, uo=4,
        use_case="Small zone controller, 4 in + 4 out",
    ),
    ControllerModel(
        id="MPZ-88", name="MACH-ProZone 88", family="mpz",
        ui=8, uo=8,
        use_case="Medium zone controller, 8 in + 8 out",
    ),

    # MACH-ProAir family — AHU controllers
    ControllerModel(
        id="MPA-33", name="MACH-ProAir 33", family="mpa",
        ui=3, uo=3, bi=8, bo=8,
        use_case="Medium AHU, 3 analog in + 3 analog out + 8 binary each",
    ),
    ControllerModel(
        id="MPA-34", name="MACH-ProAir 34", family="mpa",
        ui=3, uo=4, bi=8, bo=8,
        use_case="Medium-large AHU, 3 analog + 4 analog out + 8 binary each",
    ),
    ControllerModel(
        id="MPA-35", name="MACH-ProAir 35", family="mpa",
        ui=3, uo=5, bi=8, bo=8,
        use_case="Large AHU, 3 analog + 5 analog out + 8 binary each",
    ),
    ControllerModel(
        id="MPA-36", name="MACH-ProAir 36", family="mpa",
        ui=3, uo=6, bi=8, bo=8,
        use_case="Full AHU, 3 analog + 6 analog out + 8 binary each",
    ),

    # MACH-Pro2 — Mid-size universal
    ControllerModel(
        id="MP2", name="MACH-Pro2", family="mp2",
        ui=12, uo=8, max_expansion=3,
        use_case="Mid-size pump/plant, 12 universal in + 8 universal out",
    ),

    # MACH-ProSys — Large building / plant
    ControllerModel(
        id="MPS", name="MACH-ProSys", family="mps",
        ui=12, uo=8, max_expansion=7,
        use_case="Large plant/building controller, expandable to 180 in / 120 out",
    ),
]

# Quick lookup by ID
_CONTROLLER_MAP: Dict[str, ControllerModel] = {c.id: c for c in CONTROLLERS}

# Family preference by equipment category
FAMILY_PREFERENCE = {
    "vav":      ["rcfa", "mpz"],
    "terminal": ["rcfa", "mpz"],
    "fcu":      ["rcfa", "mpz"],
    "ahu":      ["mpa", "mps", "mp2"],
    "rtu":      ["mpa", "mps"],
    "plant":    ["mps", "mp2"],
    "pump":     ["mp2", "mps"],
    "boiler":   ["mps", "mp2"],
    "chiller":  ["mps"],
    "generic":  ["mpz", "mpa", "mp2", "mps"],
}

# Expansion module definitions
EXPANSION_MODULES = {
    "MPP-IO": {"ui": 12, "uo": 8, "desc": "MACH-ProPoint I/O (12 UI + 8 UO)"},
    "MPP-I":  {"ui": 24, "uo": 0, "desc": "MACH-ProPoint Input (24 UI)"},
    "MPP-O":  {"ui": 0, "uo": 16, "desc": "MACH-ProPoint Output (16 UO)"},
    "MPP-I-B": {"ui": 0, "uo": 0, "bi": 32, "desc": "MACH-ProPoint Binary Input (32 BI)"},
}


@dataclass
class SelectionResult:
    """Result of controller selection."""
    controller: ControllerModel
    fits: bool
    # How many of each I/O type are used vs available
    ui_used: int
    ui_available: int
    uo_used: int
    uo_available: int
    bo_used: int
    bo_available: int
    bi_used: int
    bi_available: int
    # Expansion info
    expansion_needed: bool
    expansion_modules: List[dict]
    # Spare capacity
    ui_spare: int
    uo_spare: int
    notes: List[str]

    def summary(self) -> str:
        """Human-readable selection summary."""
        lines = [
            f"Controller: {self.controller.id} ({self.controller.name})",
            f"  UI: {self.ui_used}/{self.ui_available} used"
            f"  ({self.ui_spare} spare)",
            f"  UO: {self.uo_used}/{self.uo_available} used"
            f"  ({self.uo_spare} spare)",
        ]
        if self.controller.bo > 0 or self.bo_used > 0:
            lines.append(
                f"  BO: {self.bo_used}/{self.bo_available} used"
            )
        if self.controller.bi > 0 or self.bi_used > 0:
            lines.append(
                f"  BI: {self.bi_used}/{self.bi_available} used"
            )
        if self.expansion_needed:
            lines.append("  ** EXPANSION REQUIRED **")
            for exp in self.expansion_modules:
                lines.append(f"    + {exp['id']} x{exp['qty']} ({exp['desc']})")
        for note in self.notes:
            lines.append(f"  Note: {note}")
        return "\n".join(lines)


def select_controller(
    num_ai: int = 0,
    num_ao: int = 0,
    num_di: int = 0,
    num_do: int = 0,
    equipment_category: str = "generic",
    prefer_family: Optional[str] = None,
) -> SelectionResult:
    """
    Select the best Reliable Controls controller for the given I/O requirements.

    Args:
        num_ai: Number of analog inputs needed
        num_ao: Number of analog outputs needed
        num_di: Number of digital/binary inputs needed
        num_do: Number of digital/binary outputs needed
        equipment_category: Equipment type for family preference
        prefer_family: Override family preference (e.g., "mpa", "rcfa")

    Returns:
        SelectionResult with the recommended controller and details
    """
    # Determine family preference order
    if prefer_family:
        families = [prefer_family]
    else:
        families = FAMILY_PREFERENCE.get(
            equipment_category, FAMILY_PREFERENCE["generic"]
        )

    # Try each family in preference order
    best: Optional[SelectionResult] = None

    for family in families:
        candidates = [c for c in CONTROLLERS if c.family == family]
        for ctrl in candidates:
            result = _evaluate_controller(ctrl, num_ai, num_ao, num_di, num_do)
            if result.fits:
                if best is None or _is_better_fit(result, best):
                    best = result

    # If no preferred family works, try all controllers
    if best is None:
        for ctrl in CONTROLLERS:
            result = _evaluate_controller(ctrl, num_ai, num_ao, num_di, num_do)
            if result.fits:
                if best is None or _is_better_fit(result, best):
                    best = result

    # If still nothing fits without expansion, try with expansion
    if best is None:
        for ctrl in CONTROLLERS:
            if ctrl.max_expansion > 0:
                result = _evaluate_with_expansion(
                    ctrl, num_ai, num_ao, num_di, num_do
                )
                if result.fits:
                    if best is None or _is_better_fit(result, best):
                        best = result

    # Last resort: return the largest controller with expansion notes
    if best is None:
        ctrl = _CONTROLLER_MAP["MPS"]
        best = _evaluate_with_expansion(ctrl, num_ai, num_ao, num_di, num_do)
        if not best.fits:
            best.notes.append(
                "WARNING: I/O requirements exceed maximum capacity even with expansion"
            )

    return best


def _evaluate_controller(
    ctrl: ControllerModel,
    num_ai: int, num_ao: int, num_di: int, num_do: int,
) -> SelectionResult:
    """Check if a controller can handle the I/O without expansion."""
    notes = []

    # For MPA family: separate BI/BO terminals exist
    if ctrl.family == "mpa":
        # UI handles analog inputs; BI handles digital inputs
        ui_used = num_ai
        bi_used = num_di
        # UO handles analog outputs; BO handles digital outputs
        uo_used = num_ao
        bo_used = num_do

        ui_avail = ctrl.ui
        uo_avail = ctrl.uo
        bi_avail = ctrl.bi
        bo_avail = ctrl.bo

        fits = (
            ui_used <= ui_avail
            and uo_used <= uo_avail
            and bi_used <= bi_avail
            and bo_used <= bo_avail
        )
    else:
        # Universal I/O: UI can be AI or DI, UO can be AO or DO
        ui_used = num_ai + num_di
        uo_used = num_ao + num_do
        bi_used = 0
        bo_used = 0

        ui_avail = ctrl.ui
        uo_avail = ctrl.uo + ctrl.bo  # BO slots can handle DO
        bi_avail = ctrl.bi
        bo_avail = ctrl.bo

        # For RCFA: BO terminals are separate relay outputs (DO only)
        # AO must use UO terminals; DO can use either UO or BO
        if ctrl.family == "rcfa":
            # AO needs UO terminals specifically
            if num_ao > ctrl.uo:
                fits = False
            else:
                # Remaining UO can handle some DO
                uo_remaining = ctrl.uo - num_ao
                do_from_uo = min(num_do, uo_remaining)
                do_from_bo = num_do - do_from_uo

                uo_used = num_ao + do_from_uo
                bo_used = do_from_bo

                fits = (
                    ui_used <= ui_avail
                    and uo_used <= ctrl.uo
                    and bo_used <= ctrl.bo
                )
                uo_avail = ctrl.uo
                bo_avail = ctrl.bo
        else:
            # Generic universal: UO handles AO, remaining UO + BO handle DO
            if num_ao > ctrl.uo:
                fits = False
            else:
                uo_remaining = ctrl.uo - num_ao
                do_from_uo = min(num_do, uo_remaining)

                uo_used = num_ao + do_from_uo
                bo_used = num_do - do_from_uo

                fits = (
                    ui_used <= ctrl.ui
                    and uo_used <= ctrl.uo
                    and bo_used <= ctrl.bo
                )
                uo_avail = ctrl.uo
                bo_avail = ctrl.bo

    return SelectionResult(
        controller=ctrl,
        fits=fits,
        ui_used=ui_used,
        ui_available=ui_avail,
        uo_used=uo_used,
        uo_available=uo_avail,
        bo_used=bo_used if ctrl.bo > 0 or bo_used > 0 else 0,
        bo_available=bo_avail,
        bi_used=bi_used,
        bi_available=bi_avail,
        expansion_needed=False,
        expansion_modules=[],
        ui_spare=max(0, ui_avail - ui_used),
        uo_spare=max(0, uo_avail - uo_used),
        notes=notes,
    )


def _evaluate_with_expansion(
    ctrl: ControllerModel,
    num_ai: int, num_ao: int, num_di: int, num_do: int,
) -> SelectionResult:
    """Check if a controller can handle I/O with expansion modules."""
    base_result = _evaluate_controller(ctrl, num_ai, num_ao, num_di, num_do)
    if base_result.fits:
        return base_result

    # Calculate shortfall
    ui_short = max(0, base_result.ui_used - base_result.ui_available)
    uo_short = max(0, base_result.uo_used - base_result.uo_available)

    expansion_modules = []
    total_exp = 0

    # Add MPP-IO modules to cover shortfall
    while (ui_short > 0 or uo_short > 0) and total_exp < ctrl.max_expansion:
        exp = EXPANSION_MODULES["MPP-IO"]
        ui_short -= exp["ui"]
        uo_short -= exp["uo"]
        total_exp += 1

    if ui_short <= 0 and uo_short <= 0:
        expansion_modules.append({
            "id": "MPP-IO",
            "qty": total_exp,
            "desc": EXPANSION_MODULES["MPP-IO"]["desc"],
        })
        total_ui = ctrl.ui + total_exp * EXPANSION_MODULES["MPP-IO"]["ui"]
        total_uo = ctrl.uo + total_exp * EXPANSION_MODULES["MPP-IO"]["uo"]

        return SelectionResult(
            controller=ctrl,
            fits=True,
            ui_used=base_result.ui_used,
            ui_available=total_ui,
            uo_used=base_result.uo_used,
            uo_available=total_uo,
            bo_used=base_result.bo_used,
            bo_available=base_result.bo_available,
            bi_used=base_result.bi_used,
            bi_available=base_result.bi_available,
            expansion_needed=True,
            expansion_modules=expansion_modules,
            ui_spare=max(0, total_ui - base_result.ui_used),
            uo_spare=max(0, total_uo - base_result.uo_used),
            notes=[f"Requires {total_exp} expansion module(s)"],
        )

    # Can't fit even with max expansion
    base_result.notes.append("Exceeds controller capacity with max expansion")
    return base_result


def _is_better_fit(a: SelectionResult, b: SelectionResult) -> bool:
    """Return True if 'a' is a better (tighter) fit than 'b'.
    Prefer: no expansion, fewer spare I/O (smallest controller that fits).
    """
    if a.expansion_needed != b.expansion_needed:
        return not a.expansion_needed  # prefer no expansion

    # Prefer smaller total capacity (tighter fit)
    a_total = a.ui_available + a.uo_available + a.bo_available
    b_total = b.ui_available + b.uo_available + b.bo_available
    return a_total < b_total


def get_controller(controller_id: str) -> Optional[ControllerModel]:
    """Look up a controller model by ID."""
    return _CONTROLLER_MAP.get(controller_id)


def list_controllers(family: Optional[str] = None) -> List[ControllerModel]:
    """List available controllers, optionally filtered by family."""
    if family:
        return [c for c in CONTROLLERS if c.family == family]
    return list(CONTROLLERS)
