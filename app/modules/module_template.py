"""
SBS Controls Module Template

Every module (base or feature) follows this exact structure.
Copy this file and fill in the values to create a new module.

Module Interface Specification:
    id          - Unique module identifier (e.g., "mod_chw_cooling", "base_ahu_vav")
    name        - Human-readable display name
    feature     - Feature code matching SBS Equipment Standard add-on codes
    category    - Functional category for grouping/filtering
    requires    - List of module IDs this module depends on
    conflicts   - List of module IDs that cannot coexist with this module
    exec_order  - Code execution order (10=modes, 20=occ, 30=fan, etc.)
    objects     - BACnet objects organized by type (AI, AO, AV, BI, BO, BV, etc.)
    io_map      - Physical terminal assignments (e.g., "UI1": "{device-name}-SAT")
    code        - Reliable Controls Control-BASIC program code block

Object Definition Fields:
    name        - Point name using {device-name} template (e.g., "{device-name}-SAT")
    desc        - Human-readable description
    units       - BACnet engineering units (e.g., "deg-f", "percent", "no-units")
    min         - Minimum value (for analog points)
    max         - Maximum value (for analog points)
    states      - State text dict for binary/multistate (e.g., {0: "Off", 1: "On"})
    default     - Default/relinquish-default value

Control-BASIC Code Conventions:
    - Use REM for comments
    - Point references use BACnet shorthand: AI1, AO2, AV7, BI3, BO1, BV5
    - Variables are single letters or short names: T, SP, ERR, PID_OUT
    - IF/THEN/ELSE/ENDIF block structure
    - GOTO/GOSUB for flow control
    - Standard functions: ABS(), MAX(), MIN(), INT()
    - Timer: ELAPSED (seconds since program start)
    - Network refs: {device_id}AI1 for cross-device reads
"""

# ── Template Module ──────────────────────────────────────────────────────────
# Copy this structure for new modules

MODULE_TEMPLATE = {
    "id": "mod_xxx",
    "name": "Human Readable Module Name",
    "feature": "FEATURE_CODE",
    "category": "cooling",          # cooling|heating|fan|damper|safety|etc.
    "requires": [],                 # Other module IDs this depends on
    "conflicts": [],                # Module IDs that can't coexist
    "exec_order": 50,               # 10-90 execution priority
    "objects": {
        "AI": [
            {
                "name": "{device-name}-XXX",
                "desc": "Example Analog Input",
                "units": "deg-f",
                "min": 0,
                "max": 100,
            },
        ],
        "AO": [],
        "AV": [],
        "BI": [],
        "BO": [],
        "BV": [],
    },
    "io_map": {
        # Physical terminal -> point name mapping
        # "UI1": "{device-name}-XXX",
    },
    "code": """\
REM ── Module: Example ──
REM This code block runs at exec_order priority
""",
}


# ── Example: How to register ─────────────────────────────────────────────────
#
# from app.modules import register_module
#
# module = { ... }  # Fill in structure above
# register_module(module)
