"""
Core Stubs Module — core-stubs

Provides safe-default AV/BV values for points that shared programs reference
across optional sibling modules. When a real module (e.g. heating, dsp-ctrl,
humidity, ERW, opt-start, hi-static safety) is selected, its real point wins
the assembler's name-based dedup and the stub here is skipped. When the real
module is *not* selected, the stub stands in so generated .bas code still
parses (the program reads the safe default and does nothing).

This module is processed LAST by the assembler (is_stub_fallback=True) and
skips any point whose name has already been added under inputs, outputs, or
values. It must never define a point that competes with a real module's
input/output — only fill gaps.

Auto-pulled by the AHU `core` module via `requires=["core-stubs"]`. Not used
by VVT, FCU, UV, or plant cores (they have their own architectures).

Stub instance allocation: 700-720 range — well above the highest real
instance (272) so collisions are impossible.

If you add a new shared program that references a cross-module point and the
audit flags it as missing, add a stub here rather than restructuring the
referencing program.
"""

from composition.models import Module, ValuePoint


def build():
    return Module(
        id="core-stubs",
        name="Core Stub Fallbacks",
        category="core",
        description="Safe-default AV/BV stubs for cross-module references (only used when sibling modules absent)",
        is_core=False,
        is_stub_fallback=True,

        values=[
            # Heating/cooling lockout flags (real owner: heating.py)
            ValuePoint(700, "HTG-LOCKOUT",       "BV", True,  "Heating Lockout Active (stub default)"),
            ValuePoint(701, "CLG-LOCKOUT",       "BV", False, "Cooling Lockout Active (stub default)"),
            ValuePoint(702, "HTG-LO-ICON",       "BV", False, "Heating Lockout Icon (stub default)"),
            ValuePoint(703, "CLG-LO-ICON",       "BV", True,  "Cooling Lockout Icon (stub default)"),

            # Freeze protection (real owner: heating.py)
            ValuePoint(704, "FRZ-PRTC-MODE",     "BV", False, "Freeze Protection Mode (stub default)"),
            ValuePoint(705, "FRZ-PRTC-SP",       "AV", 25.0,  "Freeze Protection OAT SP (stub default)",   "°F"),

            # ERW defrost (real owner: erw.py)
            ValuePoint(706, "ERW-DEFROST-MODE",  "BV", False, "ERW Defrost Mode (stub default)"),
            ValuePoint(707, "ERW-DEFROST-SP",    "AV", 15.0,  "ERW Defrost OAT SP (stub default)",         "°F"),

            # Optimum Start / Stop (real owner: optimum_start.py)
            ValuePoint(708, "OSC-MODE",          "BV", False, "Optimum Stop Cool Mode (stub default)"),
            ValuePoint(709, "OSH-MODE",          "BV", False, "Optimum Start Heat Mode (stub default)"),

            # Safety (real owner: safety.py — when safe-hi-static is selected, SA-HPS is a BI)
            ValuePoint(710, "SA-HPS",            "BV", True,  "Supply Air High Static (stub default — Normal)"),

            # Exhaust fan status (real owner: fan_return_exhaust.py — BI when EF module loaded)
            ValuePoint(711, "EF-S",              "BV", False, "Exhaust Fan Status (stub default)"),

            # Cooling-related (real owner: cooling.py)
            ValuePoint(712, "CHWS-CALL",         "BV", False, "CHW System Call (stub default)"),
            ValuePoint(713, "CLG-RAMP",          "AV", 0.5,   "Cooling Valve Ramp Time (stub default)",    "Min."),

            # Economizer (real owner: economizer.py)
            ValuePoint(714, "ECON-MODE",         "BV", False, "Economizer Mode (stub default)"),

            # Humidity (real owner: humidity.py — RAH is an AI when loaded)
            ValuePoint(715, "RAH",               "AV", 50.0,  "Return Air Humidity (stub default)",        "%"),
            ValuePoint(716, "RMH",               "AV", 37.4,  "Room Humidity (stub default)",              "%"),

            # DSP / VAV-only (real owner: dsp_ctrl.py)
            ValuePoint(717, "ACT-DSP",           "AV", 0.0,   "Active DSP Reading (stub default)",         "WC"),
            ValuePoint(718, "SA-DSP",            "AV", 0.0,   "Supply Air Duct Static (stub default)",     "WC"),
            ValuePoint(719, "ZONE-DMP-POS",      "AV", 100.0, "Zone Damper Position (stub default)",       "%"),

            # OA airflow (real owner: ventilation.py vent-ams uses OA-CFM AI; OA-VEL is
            # only referenced by PRG35-OAD-RAD as the velocity feeding the K-factor calc)
            ValuePoint(720, "OA-VEL",            "AV", 0.0,   "OA Velocity (stub default)",                "FPM"),

            # Preheat pump status (real owner: pump.py ph-hw-pump module)
            ValuePoint(721, "PH-PMP-STS",        "BV", False, "Preheat Pump Status (stub default)"),
        ],

        soo_paragraph="",
    )
