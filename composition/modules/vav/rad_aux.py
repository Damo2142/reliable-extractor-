"""
VAV Auxiliary Radiant Heat Module — vav-rad-aux

Optional add-on for VAV families that support reheat (single-duct HW/electric,
fan-powered, dual-duct reheat — NOT cooling-only). Adds a radiant heating valve
that is staged together with the box reheat.

Two valve options (mutually exclusive):
  vav-rad-aux-mod — modulating AO radiant valve
  vav-rad-aux-flt — floating point radiant valve, CBAS FLOAT() (same pattern as
                    vav-rh-hw-flt, with POWER-LOSS sync trigger)

Staging (HTG-DAT-LOOP = heating demand 0-100%, loop instance 5):
  STG1 enables when HTG-DAT-LOOP > 25%   STG1 drops when HTG-DAT-LOOP < 15%
  STG2 enables when HTG-DAT-LOOP > 60%   STG2 drops when HTG-DAT-LOOP < 45%

  CFG-RAD-STAGE selects which stage drives the radiant valve:
    1 = radiant is stage 1 (radiant leads, reheat adds as stage 2)
    2 = radiant is stage 2 (reheat leads, radiant adds when reheat at max)
  When the box has no reheat module, radiant is stage 1 (default CFG-RAD-STAGE=1).

Outdoor enable: radiant is always enabled — no OAT cutoff on the VAV aux module.

Floating-only config:
  CFG-RAD-DRV-TIME (default 150 sec)
  CFG-RAD-POS-DB   (default 2%)
"""

from composition.models import (
    Module, OutputPoint, ValuePoint, LoopDef, ProgramDef, SystemGroupDef
)


# Heating demand loop shared by both valve variants.
# Reverse acting: room temp below heating setpoint drives demand up.
_HTG_DAT_LOOP = LoopDef(
    5, "HTG-DAT-LOOP", "ACT-RMT", "RMT-SP-HTG", "RAD-DMD",
    p_band=4.0, integral=10.0, action="reverse",
    description="Auxiliary radiant heating demand (0-100%) from space temp deviation")


# Common staging block (shared text prepended to each valve's drive logic).
_STAGING = """\
REM --- RAD-AUX-PRG ---
REM Auxiliary radiant heat staging from heating demand (HTG-DAT-LOOP, 0-100%).
REM CFG-RAD-STAGE = 1: radiant leads (stage 1). = 2: radiant lags reheat (stage 2).
REM Radiant is always enabled — no OAT cutoff on the VAV aux module.
REM
REM --- Two-stage heating thresholds with hysteresis ---
IF HTG-DAT-LOOP > 25.0 THEN HTG-STG1 = 1
IF HTG-DAT-LOOP < 15.0 THEN HTG-STG1 = 0
IF HTG-DAT-LOOP > 60.0 THEN HTG-STG2 = 1
IF HTG-DAT-LOOP < 45.0 THEN HTG-STG2 = 0
REM
REM --- Radiant follows its assigned stage ---
IF CFG-RAD-STAGE = 1 THEN RAD-ACTIVE = HTG-STG1
IF CFG-RAD-STAGE = 2 THEN RAD-ACTIVE = HTG-STG2
REM
REM --- Radiant demand modulates across its assigned stage band ---
IF CFG-RAD-STAGE = 1 THEN RAD-DMD = SLIDE( HTG-DAT-LOOP , 25.0 , 60.0 , 0.0 , 100.0 )
IF CFG-RAD-STAGE = 2 THEN RAD-DMD = SLIDE( HTG-DAT-LOOP , 60.0 , 100.0 , 0.0 , 100.0 )
RAD-DMD = LIMIT( RAD-DMD , 0.0 , 100.0 )
IF NOT RAD-ACTIVE THEN RAD-DMD = 0.0
"""

_PRG_RAD_MOD = _STAGING + """\
REM
REM --- Drive modulating radiant valve ---
RAD-VLV = RAD-DMD
RAD-VLV-POS = RAD-VLV
"""

_PRG_RAD_FLT = _STAGING + """\
REM
REM --- Drive floating radiant valve using CBAS FLOAT() ---
RAD-POS-CMD = RAD-DMD
IF+ POWER-LOSS THEN START RAD-FLOAT-SYNC
IF+ NOT RAD-ACTIVE THEN START RAD-FLOAT-SYNC
IF TIME-ON( RAD-FLOAT-SYNC ) > 0:00:05 THEN STOP RAD-FLOAT-SYNC
RAD-POS = FLOAT( RAD-OPEN , RAD-CLOSE , RAD-POS-CMD , CFG-RAD-DRV-TIME , CFG-RAD-POS-DB , RAD-FLOAT-SYNC )
"""


# Staging values shared by both variants.
def _staging_values():
    return [
        ValuePoint(120, "RAD-DMD",       "AV", 0.0,   "Radiant Heating Demand",         "%"),
        ValuePoint(121, "CFG-RAD-STAGE", "AV", 1.0,   "Radiant Stage (1=lead 2=lag)",   ""),
        ValuePoint(120, "HTG-STG1",      "BV", False, "Heating Stage 1 Active"),
        ValuePoint(121, "HTG-STG2",      "BV", False, "Heating Stage 2 Active"),
        ValuePoint(122, "RAD-ACTIVE",    "BV", False, "Radiant Stage Active"),
    ]


_SOO = """The VAV terminal unit shall include an auxiliary radiant heating valve staged
with the box reheat. A two-stage heating demand derived from space temperature
deviation shall enable stage one above twenty-five percent and stage two above
sixty percent, with hysteresis on the drop points. A configurable stage assignment
shall determine whether the radiant valve leads (stage one) or lags the reheat
(stage two). When the box has no reheat the radiant valve is stage one. The radiant
valve shall have no outdoor air temperature cutoff."""


def build_rad_aux_mod():
    """Modulating AO auxiliary radiant valve."""
    return Module(
        id="vav-rad-aux-mod",
        name="Aux Radiant Heat (Modulating)",
        category="aux-heat",
        description="Auxiliary radiant heating valve (modulating AO) staged with box reheat",
        is_core=False,
        outputs=[
            OutputPoint(3, "RAD-VLV", "AO", "0.0 ->100%", "Radiant Heat Valve", 2.0, 10.0, False, "%"),
        ],
        values=_staging_values() + [
            ValuePoint(123, "RAD-VLV-POS", "AV", 0.0, "Radiant Valve Position (tracked)", "%"),
        ],
        loops=[_HTG_DAT_LOOP],
        programs=[
            ProgramDef(14, "RAD-AUX-PRG", "PRG14-RAD-AUX.bas", _PRG_RAD_MOD, True,
                       "Auxiliary radiant heat staging — modulating valve", exec_order=14),
        ],
        system_groups=[
            SystemGroupDef("{device-name}-RADIANT", "Auxiliary radiant heat staging and valve"),
        ],
        soo_paragraph=_SOO,
        requires=["vav-core"],
        conflicts=["vav-rad-aux-flt"],
        mutually_exclusive_group="vav-rad-aux",
    )


def build_rad_aux_flt():
    """Floating point auxiliary radiant valve (CBAS FLOAT())."""
    return Module(
        id="vav-rad-aux-flt",
        name="Aux Radiant Heat (Floating)",
        category="aux-heat",
        description="Auxiliary radiant heating valve (floating BO open/close, FLOAT()) staged with box reheat",
        is_core=False,
        outputs=[
            OutputPoint(3, "RAD-OPEN",  "BO", "Off/On", "Radiant Valve Open",  units=""),
            OutputPoint(4, "RAD-CLOSE", "BO", "Off/On", "Radiant Valve Close", units=""),
        ],
        values=_staging_values() + [
            ValuePoint(123, "RAD-POS",          "AV", 0.0,   "Radiant Valve Actual Position",    "%"),
            ValuePoint(124, "RAD-POS-CMD",      "AV", 0.0,   "Radiant Valve Commanded Position", "%"),
            ValuePoint(125, "CFG-RAD-DRV-TIME", "AV", 150.0, "Radiant Valve Full Stroke Time",   "Sec."),
            ValuePoint(126, "CFG-RAD-POS-DB",   "AV", 2.0,   "Radiant Float Position Deadband",  "%"),
            ValuePoint(123, "RAD-FLOAT-SYNC",   "BV", False, "Radiant Float Sync Trigger"),
        ],
        loops=[_HTG_DAT_LOOP],
        programs=[
            ProgramDef(14, "RAD-AUX-PRG", "PRG14-RAD-AUX.bas", _PRG_RAD_FLT, True,
                       "Auxiliary radiant heat staging — floating valve", exec_order=14),
        ],
        system_groups=[
            SystemGroupDef("{device-name}-RADIANT", "Auxiliary radiant heat staging and valve"),
        ],
        soo_paragraph=_SOO,
        requires=["vav-core"],
        conflicts=["vav-rad-aux-mod"],
        mutually_exclusive_group="vav-rad-aux",
    )
