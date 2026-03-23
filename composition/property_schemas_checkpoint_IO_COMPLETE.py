"""
SBS Composition Engine — .pan Block Property Schemas

Ground truth source: blank .panx files from RC Studio + RC Studio upload files.
CRC: CRC-16/KERMIT, init=0xF321, over block[12:] payload only.

TLV Record format:
    [total_len 1B] [pad=0x00] [ctx_hi 1B] [ctx_lo 1B] [prop_id 1B] [value_tag 1B] [value_data...] [0x00 term]
    Payload starts with 3 bytes 00 00 00 padding before first record.

Tag reference:
    0x10 = bool FALSE (0 data bytes)
    0x11 = bool TRUE (0 data bytes)
    0x21 = uint8 (1 data byte + 00 term)
    0x22 = uint16 BE (2 data bytes + 00 term)
    0x44 = float BE IEEE754 (4 data bytes + 00 term)
    0x71 = enum/null (1 data byte + 00 term)
    0x73 = active-text string ([00] [string] [00 term])
    0x74 = inactive-text string ([00] [string] [00 term])
    0x75 = string ([len 1B] [00] [string bytes] [00 term])
    0x82 = object ref (2-3 data bytes + 00 term)
    0x91 = uint8 alt (1 data byte + 00 term)
    0x0c = BACnet ObjID BE32 (4 data bytes)
    0x65 = bytecode block (variable, for PROGRAM code)
    0xa4 = event-timestamp special (4+ bytes)
    0xb4 = event-timestamp special2 (4+ bytes)

Context namespaces:
    0x0000 = standard BACnet properties
    0x0001 = alarm/event notification properties

IMPORTANT: Units are split into two categories:
    1. Standard BACnet Engineering Units (ASHRAE 135 clause 21) → UNITS_ENUM
       Universal, safe, portable between RC Studio installations.
    2. Custom Units (BV/MV state enumerations) → stored in Custom Units tab
       NOT portable between PCs. Must be embedded or shipped alongside .pan.
    0x0004 = Reliable Controls vendor-specific properties
    0x0100 = terminal/hardware properties
"""


# ============================================================
# Standard BACnet Engineering Units (ASHRAE 135 clause 21)
# ============================================================
# Extracted from blank .panx files + RC Studio upload files.
# Cross-referenced with BACnet enumeration and SBS module definitions.
#
# Key: string used in SBS Composition Tool (InputPoint.units, ValuePoint.units, etc.)
# Value: byte value stored in .pan block prop 0x75, tag 0x91
#
# Only STANDARD BACnet units go here. Custom MV/BV state enumerations
# are defined per-project in the Custom Units Excel tab and are NOT portable.

UNITS_ENUM = {
    # Temperature
    "°F":           0x40,   # 64  degrees-fahrenheit
    "°C":           0x41,   # 65  degrees-celsius (not seen in blanks but standard)
    # Pressure
    "WC":           0x3A,   # 58  inches-of-water
    "PSI":          0x38,   # 56  pounds-per-square-inch
    # Flow / velocity
    "CFM":          0x54,   # 84  cubic-feet-per-minute
    "FPM":          0x4E,   # 78  feet-per-minute
    "GPM":          0x52,   # 82  gallons-per-minute
    # Concentration
    "ppm":          0x60,   # 96  parts-per-million
    # Percentage
    "%":            0x62,   # 98  percent
    # Time
    "Time":         0x48,   # 72  minutes (generic "Time" maps to minutes)
    "Min.":         0x48,   # 72  minutes
    "Sec":          0x49,   # 73  seconds
    # Length
    "in":           0x20,   # 32  inches (duct diameter etc.)
    # Energy
    "BTU/lb":       0x1D,   # 29  btus-per-pound (enthalpy)
    # Electrical
    "Volts":        0x14,   # 20  volts
    "kWh":          0x47,   # 71  kilowatt-hours
    "kW":           0x75,   # 117 kilowatts
    # No units / dimensionless
    "":             0x5F,   # 95  no-units
    "#":            0x5F,   # 95  no-units (count/index)
    "no-units":     0x5F,   # 95  no-units
}


def infer_point_type(units: str, states: str = "") -> str:
    """Infer the actual binary point type from units and states.

    The Excel Type column (AV/BV/MV) is documentation only.
    Always use this function to determine binary type.

    Args:
        units: Units string from the Excel/config (e.g. "°F", "Off/On", "1=Occ/2=Byp")
        states: States string, may contain "1=X / 2=Y" format

    Returns:
        "MV" if multi-state values detected
        "BV" if binary on/off
        "AV" for everything else (analog)
    """
    # Check states first — "1=X / 2=Y" or "1-X/2-Y" format → MV
    if states and ("=" in states or ("1-" in states and "2-" in states)):
        return "MV"

    # Check units for binary patterns → BV
    if units in ("Off/On", "On/Off", "Stop/Start", "Close/Open",
                 "Normal/Alarm", "Clean/Dirty"):
        return "BV"

    # Everything else → AV
    return "AV"


# ============================================================
# AV — Analog Value (type 2)
# ============================================================
# Source: blank MACH-ProAir-18.panx, AV inst=1-5,7
# Cross-checked: 149 AV blocks across RC Studio uploads

AV_PROPERTIES = [
    # (ctx, prop_id, tag, source, encoding, notes)
    # --- Context 0x0000: Standard BACnet properties ---
    (0x0000, 0x11, 0x21, "FIXED",      "uint8",             "polarity — 0x01"),
    (0x0000, 0x16, 0x44, "FIXED",      "float_be",          "increment — 0.1"),
    (0x0000, 0x19, 0x44, "FIXED",      "float_be",          "min-present-value — 0.0"),
    (0x0000, 0x1C, 0x75, "FROM_EXCEL", "string",            "description — ValuePoint.description"),
    (0x0000, 0x23, 0x82, "FIXED",      "obj_ref",           "system-group-ref — 0x050000"),
    (0x0000, 0x2D, 0x44, "FIXED",      "float_be",          "max-value — 1000.0"),
    (0x0000, 0x34, 0x82, "FIXED",      "obj_ref",           "system-group-ref2 — 0x06C000"),
    (0x0000, 0x3B, 0x44, "FIXED",      "float_be",          "min-value — -1000.0"),
    (0x0000, 0x48, 0x91, "FIXED",      "uint8",             "notification-class — 0x00"),
    (0x0000, 0x4D, 0x75, "FROM_EXCEL", "mu_header",         "Mu object name — {device-name}-POINTNAME"),
    (0x0000, 0x51, 0x10, "FIXED",      "bool",              "out-of-service — FALSE"),
    (0x0000, 0x55, 0x44, "FROM_EXCEL", "float_be",          "present-value — ValuePoint.default"),
    (0x0000, 0x57, 0x00, "FIXED",      "priority_array",    "priority-array — 22B zeros/nulls"),
    (0x0000, 0x68, 0x44, "FROM_EXCEL", "float_be",          "relinquish-default — ValuePoint.default"),
    (0x0000, 0x71, 0x21, "FIXED",      "uint8",             "status-flags — 0x00"),
    (0x0000, 0x75, 0x91, "FROM_EXCEL", "uint8",             "units — unit enum from ValuePoint.units"),
    # --- Context 0x0001: Alarm/event properties ---
    (0x0001, 0x60, 0x75, "FIXED",      "string_triple",     "event-texts — 'Out of Range'/'%s Fault'/'Out of Range'"),
    (0x0001, 0x61, 0x11, "FIXED",      "bool",              "event-detection-enable — TRUE"),
    (0x0001, 0x62, 0x10, "FIXED",      "bool",              "event-enable — FALSE"),
    (0x0001, 0x63, 0x0c, "FIXED",      "objid_plus",        "notif-class-ref — 0xFFFFFFFF + 19 55 00 tail"),
    (0x0001, 0x64, 0x21, "FIXED",      "uint8",             "notify-type — 0x00"),
    # --- Context 0x0004: Vendor-specific (Reliable Controls) ---
    (0x0004, 0x02, 0x21, "FIXED",      "uint8",             "vendor 0x0402 — 0x00"),
    (0x0004, 0x1D, 0x91, "FROM_EXCEL", "uint8",             "range code — from config"),
    (0x0004, 0x56, 0x11, "FIXED",      "bool",              "vendor 0x0456 — TRUE"),
    # --- Context 0x0100: Terminal ---
    (0x0100, 0x09, 0x91, "COMPUTED",   "uint8",             "terminal ref — instance-based"),
]


# ============================================================
# AI — Analog Input (type 0)
# ============================================================
# Source: blank MACH-ProAir-18.panx, AI inst=4,5
# NOTE: Same structure as AV but different vendor props
#       and no priority-array/relinquish-default/units in std section

AI_PROPERTIES = [
    # --- Context 0x0000: Standard ---
    (0x0000, 0x11, 0x21, "FIXED",      "uint8",             "polarity — 0x01"),
    (0x0000, 0x16, 0x44, "FIXED",      "float_be",          "increment — 0.2"),
    (0x0000, 0x19, 0x44, "FIXED",      "float_be",          "min-present-value — 0.0"),
    (0x0000, 0x1C, 0x75, "FROM_EXCEL", "string",            "description — InputPoint.description"),
    (0x0000, 0x23, 0x82, "FIXED",      "obj_ref",           "system-group-ref — 0x050000"),
    (0x0000, 0x2D, 0x44, "FIXED",      "float_be",          "max-value — 1000.0"),
    (0x0000, 0x34, 0x82, "FIXED",      "obj_ref",           "system-group-ref2 — 0x06C000"),
    (0x0000, 0x3B, 0x44, "FIXED",      "float_be",          "min-value — -1000.0"),
    (0x0000, 0x48, 0x91, "FIXED",      "uint8",             "notification-class — 0x00"),
    (0x0000, 0x4D, 0x75, "FROM_EXCEL", "mu_header",         "Mu object name — {device-name}-POINTNAME"),
    (0x0000, 0x51, 0x10, "FIXED",      "bool",              "out-of-service — FALSE"),
    (0x0000, 0x55, 0x44, "FIXED",      "float_be",          "present-value — 0.0 (read-only input)"),
    (0x0000, 0x71, 0x21, "FIXED",      "uint8",             "status-flags — 0x00"),
    # --- Context 0x0001: Alarm/event ---
    (0x0001, 0x60, 0x75, "FIXED",      "string_triple",     "event-texts — 'Out of Range'/'%s Fault'/'Out of Range'"),
    (0x0001, 0x61, 0x11, "FIXED",      "bool",              "event-detection-enable — TRUE"),
    (0x0001, 0x62, 0x10, "FIXED",      "bool",              "event-enable — FALSE"),
    (0x0001, 0x63, 0x0c, "FIXED",      "objid_plus",        "notif-class-ref — 0xFFFFFFFF + tail"),
    (0x0001, 0x64, 0x21, "FIXED",      "uint8",             "notify-type — 0x00"),
    # --- Context 0x0004: Vendor-specific ---
    (0x0004, 0x1E, 0x11, "FIXED",      "bool",              "vendor 0x041E — TRUE"),
    (0x0004, 0x1F, 0x44, "FIXED",      "float_be",          "vendor 0x041F — 0.0"),
    (0x0004, 0x20, 0x21, "FROM_EXCEL", "uint8",             "range code — 0x00 or 0x02 etc from InputPoint.range_code"),
    (0x0004, 0x56, 0x11, "FIXED",      "bool",              "vendor 0x0456 — TRUE"),
    # --- Context 0x0100: Terminal ---
    (0x0100, 0x09, 0x91, "COMPUTED",   "uint8",             "terminal ref — InputPoint.row"),
]


# ============================================================
# BI — Binary Input (type 3)
# ============================================================
# Source: blank MACH-ProAir-18.panx, BI inst=6

BI_PROPERTIES = [
    # --- Context 0x0000: Standard ---
    (0x0000, 0x04, 0x74, "FIXED",      "text",              "active-text — 'Yes'"),
    (0x0000, 0x06, 0x91, "FIXED",      "uint8",             "change-of-state-count — 0x00"),
    (0x0000, 0x10, 0xa4, "FIXED",      "event_timestamps",  "event-type-flags — a4 FFFFFFFF b4 FFFFFFFF 00"),
    (0x0000, 0x11, 0x21, "FIXED",      "uint8",             "polarity — 0x01"),
    (0x0000, 0x1C, 0x75, "FROM_EXCEL", "string",            "description — InputPoint.description"),
    (0x0000, 0x21, 0x21, "FIXED",      "uint8",             "feedback-value — 0x00"),
    (0x0000, 0x23, 0x82, "FIXED",      "obj_ref",           "system-group-ref — 0x050000"),
    (0x0000, 0x2E, 0x73, "FIXED",      "text",              "inactive-text — 'No'"),
    (0x0000, 0x48, 0x91, "FIXED",      "uint8",             "notification-class — 0x00"),
    (0x0000, 0x4D, 0x75, "FROM_EXCEL", "mu_header",         "Mu object name — {device-name}-POINTNAME"),
    (0x0000, 0x51, 0x10, "FIXED",      "bool",              "out-of-service — FALSE"),
    (0x0000, 0x54, 0x91, "FIXED",      "uint8",             "polarity2 — 0x00"),
    # --- Context 0x0001: Alarm/event ---
    (0x0001, 0x60, 0x75, "FIXED",      "string_triple",     "event-texts — 'Change of State'/'%s Fault'/'Change of State'"),
    (0x0001, 0x61, 0x11, "FIXED",      "bool",              "event-detection-enable — TRUE"),
    (0x0001, 0x62, 0x10, "FIXED",      "bool",              "event-enable — FALSE"),
    (0x0001, 0x63, 0x0c, "FIXED",      "objid_plus",        "notif-class-ref — 0xFFFFFFFF + tail"),
    (0x0001, 0x64, 0x21, "FIXED",      "uint8",             "notify-type — 0x00"),
    # --- Context 0x0004: Vendor-specific ---
    (0x0004, 0x1E, 0x11, "FIXED",      "bool",              "vendor 0x041E — TRUE"),
    (0x0004, 0x39, 0x91, "FIXED",      "uint8",             "vendor 0x0439 — 0x00"),
    (0x0004, 0x3B, 0x11, "FIXED",      "bool",              "vendor 0x043B — TRUE"),
    (0x0004, 0x58, 0x21, "FIXED",      "uint8",             "vendor 0x0458 — 0x64 (100)"),
]


# ============================================================
# BO — Binary Output (type 4)
# ============================================================
# Source: blank MACH-ProAir-18.panx, BO inst=8

BO_PROPERTIES = [
    # --- Context 0x0000: Standard ---
    (0x0000, 0x04, 0x74, "FIXED",      "text",              "active-text — 'Yes'"),
    (0x0000, 0x0F, 0x21, "FIXED",      "uint8",             "event-state — 0x00"),
    (0x0000, 0x10, 0xa4, "FIXED",      "event_timestamps",  "event-type-flags — a4 FFFFFFFF b4 FFFFFFFF 00"),
    (0x0000, 0x11, 0x21, "FIXED",      "uint8",             "polarity — 0x01"),
    (0x0000, 0x1C, 0x75, "FROM_EXCEL", "string",            "description — OutputPoint.description"),
    (0x0000, 0x21, 0x21, "FIXED",      "uint8",             "feedback-value — 0x00"),
    (0x0000, 0x23, 0x82, "FIXED",      "obj_ref",           "system-group-ref — 0x050000"),
    (0x0000, 0x2E, 0x73, "FIXED",      "text",              "inactive-text — 'No'"),
    (0x0000, 0x42, 0x21, "FIXED",      "uint8",             "min-off-time — 0x00"),
    (0x0000, 0x43, 0x21, "FIXED",      "uint8",             "min-on-time — 0x00"),
    (0x0000, 0x4D, 0x75, "FROM_EXCEL", "mu_header",         "Mu object name — {device-name}-POINTNAME"),
    (0x0000, 0x51, 0x10, "FIXED",      "bool",              "out-of-service — FALSE"),
    (0x0000, 0x54, 0x91, "FIXED",      "uint8",             "polarity2 — 0x00"),
    (0x0000, 0x57, 0x00, "FIXED",      "priority_array",    "priority-array — binary version"),
    (0x0000, 0x68, 0x91, "FIXED",      "uint8",             "relinquish-default — 0x00"),
    # --- Context 0x0001: Alarm/event ---
    (0x0001, 0x60, 0x75, "FIXED",      "string_triple",     "event-texts — 'Command Failure'/'%s Fault'/'Command Failure'"),
    (0x0001, 0x61, 0x11, "FIXED",      "bool",              "event-detection-enable — TRUE"),
    (0x0001, 0x62, 0x10, "FIXED",      "bool",              "event-enable — FALSE"),
    (0x0001, 0x63, 0x0c, "FIXED",      "objid_plus",        "notif-class-ref — 0xFFFFFFFF + tail"),
    (0x0001, 0x64, 0x21, "FIXED",      "uint8",             "notify-type — 0x00"),
    # --- Context 0x0004: Vendor-specific ---
    (0x0004, 0x13, 0xc4, "FIXED",      "special",           "vendor 0x0413 — c4 FFFFFFFF 00"),
    (0x0004, 0x1D, 0x91, "FROM_EXCEL", "uint8",             "range code — from OutputPoint.range_code"),
    (0x0004, 0x1E, 0x11, "FIXED",      "bool",              "vendor 0x041E — TRUE"),
    (0x0004, 0x58, 0x21, "FIXED",      "uint8",             "vendor 0x0458 — 0x64 (100)"),
]


# ============================================================
# AO — Analog Output (type 1)
# ============================================================
# Source: RC Studio VAV-IS1000ME (only 1 AO block available)
# NOTE: Structure matches AV closely — analog output with priority array

AO_PROPERTIES = [
    # --- Context 0x0000: Standard ---
    (0x0000, 0x11, 0x21, "FIXED",      "uint8",             "polarity — 0x01"),
    (0x0000, 0x16, 0x44, "FIXED",      "float_be",          "increment — 0.1"),
    (0x0000, 0x19, 0x44, "FIXED",      "float_be",          "min-present-value — 0.0"),
    (0x0000, 0x1C, 0x71, "FROM_EXCEL", "enum_or_string",    "description — may use 0x71 (null) or 0x75 (string)"),
    (0x0000, 0x23, 0x82, "FIXED",      "obj_ref",           "system-group-ref — 0x050000"),
    (0x0000, 0x2D, 0x44, "FIXED",      "float_be",          "max-value — 1000.0"),
    (0x0000, 0x34, 0x82, "FIXED",      "obj_ref",           "system-group-ref2 — 0x06C000"),
    (0x0000, 0x3B, 0x44, "FIXED",      "float_be",          "min-value — -1000.0"),
    (0x0000, 0x48, 0x91, "FIXED",      "uint8",             "notification-class — 0x00"),
    (0x0000, 0x4D, 0x75, "FROM_EXCEL", "mu_header",         "Mu object name — {device-name}-POINTNAME"),
    (0x0000, 0x51, 0x10, "FIXED",      "bool",              "out-of-service — FALSE"),
    (0x0000, 0x55, 0x44, "FROM_EXCEL", "float_be",          "present-value — 0.0"),
    (0x0000, 0x57, 0x00, "FIXED",      "priority_array",    "priority-array — analog version"),
    (0x0000, 0x68, 0x44, "FIXED",      "float_be",          "relinquish-default — 0.0"),
    (0x0000, 0x71, 0x21, "FIXED",      "uint8",             "status-flags — 0x00"),
    (0x0000, 0x75, 0x91, "FROM_EXCEL", "uint8",             "units — unit enum"),
    # --- Context 0x0001: Alarm/event ---
    (0x0001, 0x60, 0x75, "FIXED",      "string_triple",     "event-texts — 'Out of Range'/'%s Fault'/'Out of Range'"),
    (0x0001, 0x61, 0x11, "FIXED",      "bool",              "event-detection-enable — TRUE"),
    (0x0001, 0x62, 0x10, "FIXED",      "bool",              "event-enable — FALSE"),
    (0x0001, 0x63, 0x0c, "FIXED",      "objid_plus",        "notif-class-ref — 0xFFFFFFFF + tail"),
    (0x0001, 0x64, 0x21, "FIXED",      "uint8",             "notify-type — 0x00"),
    # --- Context 0x0004: Vendor-specific ---
    (0x0004, 0x02, 0x21, "FIXED",      "uint8",             "vendor 0x0402 — 0x00"),
    (0x0004, 0x1D, 0x91, "FROM_EXCEL", "uint8",             "range code — from OutputPoint.range_code"),
    (0x0004, 0x1E, 0x10, "FIXED",      "bool",              "vendor 0x041E — FALSE"),
    (0x0004, 0x22, 0x44, "FIXED",      "float_be",          "vendor 0x0422 — 0.0"),
    (0x0004, 0x23, 0x44, "FIXED",      "float_be",          "vendor 0x0423 — 10.125 (max voltage)"),
    (0x0004, 0x56, 0x10, "FIXED",      "bool",              "vendor 0x0456 — FALSE"),
    # --- Context 0x0100: Terminal ---
    (0x0100, 0x09, 0x91, "COMPUTED",   "uint8",             "terminal ref — OutputPoint.row"),
]


# ============================================================
# BV — Binary Value (type 5)
# ============================================================
# Source: blank MACH-ProAir-18.panx, BV inst=6

BV_PROPERTIES = [
    # --- Context 0x0000: Standard ---
    (0x0000, 0x04, 0x74, "FIXED",      "text",              "active-text — 'Yes'"),
    (0x0000, 0x06, 0x91, "FIXED",      "uint8",             "change-of-state-count — 0x00"),
    (0x0000, 0x10, 0xa4, "FIXED",      "event_timestamps",  "event-type-flags — a4 FFFFFFFF b4 FFFFFFFF 00"),
    (0x0000, 0x11, 0x21, "FIXED",      "uint8",             "polarity — 0x01"),
    (0x0000, 0x1C, 0x75, "FROM_EXCEL", "string",            "description — ValuePoint.description"),
    (0x0000, 0x21, 0x21, "FIXED",      "uint8",             "feedback-value — 0x00"),
    (0x0000, 0x23, 0x82, "FIXED",      "obj_ref",           "system-group-ref — 0x050000"),
    (0x0000, 0x2E, 0x73, "FIXED",      "text",              "inactive-text — 'No'"),
    (0x0000, 0x42, 0x21, "FIXED",      "uint8",             "min-off-time — 0x00"),
    (0x0000, 0x4D, 0x75, "FROM_EXCEL", "mu_header",         "Mu object name — {device-name}-POINTNAME"),
    (0x0000, 0x51, 0x10, "FIXED",      "bool",              "out-of-service — FALSE"),
    (0x0000, 0x55, 0x91, "FROM_EXCEL", "uint8",             "present-value — 0x00 or 0x01"),
    (0x0000, 0x57, 0x00, "FIXED",      "priority_array",    "priority-array — binary version"),
    (0x0000, 0x68, 0x91, "FIXED",      "uint8",             "relinquish-default — 0x00"),
    # --- Context 0x0001: Alarm/event ---
    (0x0001, 0x60, 0x75, "FIXED",      "string_triple",     "event-texts — 'Change of State'/'%s Fault'/'Change of State'"),
    (0x0001, 0x61, 0x11, "FIXED",      "bool",              "event-detection-enable — TRUE"),
    (0x0001, 0x62, 0x10, "FIXED",      "bool",              "event-enable — FALSE"),
    (0x0001, 0x63, 0x0c, "FIXED",      "objid_plus",        "notif-class-ref — 0xFFFFFFFF + tail"),
    (0x0001, 0x64, 0x21, "FIXED",      "uint8",             "notify-type — 0x00"),
    # --- Context 0x0004: Vendor-specific ---
    (0x0004, 0x3B, 0x11, "FIXED",      "bool",              "vendor 0x043B — TRUE"),
    (0x0004, 0x58, 0x21, "FIXED",      "uint8",             "vendor 0x0458 — 0x64 (100)"),
]


# ============================================================
# LOOP — PID Loop (type 12)
# ============================================================
# Source: RC Studio VVT-BYP-ISV000E.pan, LOOP inst=1

LOOP_PROPERTIES = [
    # --- Context 0x0000: Standard ---
    (0x0000, 0x02, 0x91, "FROM_EXCEL", "uint8",             "action — 0x00=direct, 0x01=reverse"),
    (0x0000, 0x0E, 0x44, "FIXED",      "float_be",          "derivative — 0.0"),
    (0x0000, 0x11, 0x21, "FIXED",      "uint8",             "polarity — 0x01"),
    (0x0000, 0x13, 0x0c, "FROM_EXCEL", "objid_be32",        "controlled-variable-ref — input ObjID"),
    (0x0000, 0x16, 0x44, "FIXED",      "float_be",          "increment — 0.1"),
    (0x0000, 0x19, 0x44, "FIXED",      "float_be",          "min-present-value — 0.0"),
    (0x0000, 0x1B, 0x91, "FIXED",      "uint8",             "controlled-var-units — 0x5F (95)"),
    (0x0000, 0x1C, 0x71, "FIXED",      "enum",              "description — 0x00 (null/empty)"),
    (0x0000, 0x22, 0x44, "FIXED",      "float_be",          "error — 0.0"),
    (0x0000, 0x23, 0x82, "FIXED",      "obj_ref",           "system-group-ref — 0x050000"),
    (0x0000, 0x31, 0x44, "FIXED",      "float_be",          "output — 0.0"),
    (0x0000, 0x32, 0x91, "FIXED",      "uint8",             "output-units — 0x47 (71)"),
    (0x0000, 0x3C, 0x0c, "FIXED",      "objid_be32",        "manipulated-var-ref — 0xFFFFFFFF (null)"),
    (0x0000, 0x48, 0x91, "FIXED",      "uint8",             "notification-class — 0x00"),
    (0x0000, 0x4D, 0x75, "FROM_EXCEL", "mu_header",         "Mu object name — {device-name}-LOOPNAME"),
    (0x0000, 0x51, 0x10, "FIXED",      "bool",              "out-of-service — FALSE"),
    (0x0000, 0x52, 0x91, "FROM_EXCEL", "uint8",             "present-value units — unit enum"),
    (0x0000, 0x55, 0x44, "FIXED",      "float_be",          "present-value — 0.0"),
    (0x0000, 0x58, 0x21, "FIXED",      "uint8",             "priority — 0x0A (10)"),
    (0x0000, 0x5D, 0x44, "FIXED",      "float_be",          "setpoint — 0.0"),
    (0x0000, 0x5E, 0x91, "FIXED",      "uint8",             "setpoint-units — 0x5F (95)"),
    (0x0000, 0x6C, 0x44, "FROM_EXCEL", "float_be",          "integral — minutes (e.g. 1.0)"),
    (0x0000, 0x6D, 0x0e, "FROM_EXCEL", "loop_refs",         "setpoint-ref — complex ref structure"),
    (0x0000, 0x71, 0x21, "FIXED",      "uint8",             "status-flags — 0x00"),
    # --- Context 0x0001: Alarm/event ---
    (0x0001, 0x60, 0x75, "FIXED",      "string_triple",     "event-texts — 'Floating Limit'/..."),
    (0x0001, 0x61, 0x11, "FIXED",      "bool",              "event-detection-enable — TRUE"),
    (0x0001, 0x63, 0x0c, "FIXED",      "objid_plus",        "notif-class-ref — 0xFFFFFFFF + tail"),
    (0x0001, 0x64, 0x21, "FIXED",      "uint8",             "notify-type — 0x00"),
    # --- Context 0x0004: Vendor-specific ---
    (0x0004, 0x4D, 0x44, "FROM_EXCEL", "float_be",          "p-band — proportional band"),
    # --- Context 0x0100: Terminal ---
    (0x0100, 0x09, 0x91, "COMPUTED",   "uint8",             "terminal ref"),
]


# ============================================================
# PROGRAM — Control Program (type 16)
# ============================================================
# Source: RC Studio VVT-BYP-ISV000E.pan, PRG inst=1,2
# NOTE: Bytecode data in vendor prop 0x0429 tag 0x65

PROGRAM_PROPERTIES = [
    # --- Context 0x0000: Standard ---
    (0x0000, 0x4D, 0x75, "FROM_EXCEL", "mu_header",         "Mu object name — {device-name}-PRGNAME"),
    (0x0000, 0x1C, 0x71, "FIXED",      "enum",              "description — 0x00 (null)"),
    # --- Context 0x0004: Vendor-specific ---
    (0x0004, 0x41, 0x10, "FIXED",      "bool",              "program-enabled — FALSE (starts disabled)"),
    (0x0004, 0x29, 0x65, "FROM_EXCEL", "bytecode",          "compiled CBAS bytecode — from ProgramDef.code"),
    (0x0004, 0x0A, 0x91, "FIXED",      "uint8",             "vendor 0x040A — 0x01"),
]


# ============================================================
# SCHEDULE — Weekly Schedule (type 17)
# ============================================================
# Source: RC Studio VAV-IS10P02E.pan, SCHEDULE inst=1 — DONE

SCHEDULE_PROPERTIES = [
    # Source: RC Studio VAV-IS10P02E.pan, SCHEDULE inst=1
    # --- Context 0x0000: Standard ---
    (0x0000, 0x1C, 0x71, "FIXED",      "enum",              "description — 0x00 (null)"),
    (0x0000, 0x20, 0xa4, "FIXED",      "event_timestamps",  "effective-period — a4 FFFFFFFF a4 FFFFFFFF 00"),
    (0x0000, 0x4D, 0x75, "FROM_EXCEL", "mu_header",         "Mu object name — {device-name}-LOCAL-SCHED"),
    (0x0000, 0x51, 0x10, "FIXED",      "bool",              "out-of-service — FALSE"),
    (0x0000, 0x58, 0x21, "FIXED",      "uint8",             "priority — 0x0A (10)"),
    (0x0000, 0x7B, 0x0e, "FIXED",      "weekly_schedule",   "weekly-schedule — 7-day schedule data block"),
    (0x0000, 0xAE, 0x91, "FROM_EXCEL", "uint8",             "schedule-default — default state index"),
    # --- Context 0x0004: Vendor-specific ---
    (0x0004, 0x00, 0x1c, "FIXED",      "calendar_ref",      "calendar reference data"),
    (0x0004, 0x1D, 0x91, "FROM_EXCEL", "uint8",             "range — schedule type enum (0x11=17)"),
    # --- Context 0x0005: Extended vendor ---
    (0x0005, 0x2D, 0x1c, "FIXED",      "calendar_ref",      "calendar reference data 2"),
]


# ============================================================
# TREND — Trend Log (type 20)
# ============================================================
# Source: RC Studio VVT-BYP-ISV000E.pan, TREND inst=3006,4008

TREND_PROPERTIES = [
    # --- Context 0x0000: Standard ---
    (0x0000, 0x11, 0x21, "FIXED",      "uint8",             "polarity — 0x41"),
    (0x0000, 0x23, 0x82, "FIXED",      "obj_ref",           "system-group-ref — 0x050000"),
    (0x0000, 0x7E, 0x21, "FIXED",      "uint8",             "record-count — 0x64 (100)"),
    (0x0000, 0x90, 0x10, "FIXED",      "bool",              "stop-when-full — FALSE"),
]


# ============================================================
# MV — Multi-state Value (type 19)
# ============================================================
# Source: RC Studio VAV-IS10P02E.pan, MV inst=16,17 — DONE

MV_PROPERTIES = [
    # Source: RC Studio VAV-IS10P02E.pan, MV inst=16 "MODE-OCC", inst=17 "MODE-HVAC"
    # --- Context 0x0000: Standard ---
    (0x0000, 0x11, 0x21, "FIXED",      "uint8",             "polarity — 0x01"),
    (0x0000, 0x1C, 0x71, "FIXED",      "enum",              "description — 0x00 (null)"),
    (0x0000, 0x23, 0x82, "FIXED",      "obj_ref",           "system-group-ref — 0x050000"),
    (0x0000, 0x48, 0x91, "FIXED",      "uint8",             "notification-class — 0x00"),
    (0x0000, 0x4D, 0x75, "FROM_EXCEL", "mu_header",         "Mu object name — {device-name}-POINTNAME"),
    (0x0000, 0x51, 0x10, "FIXED",      "bool",              "out-of-service — FALSE"),
    (0x0000, 0x55, 0x21, "FROM_EXCEL", "uint8",             "present-value — state index (1-based)"),
    (0x0000, 0x57, 0x00, "FIXED",      "priority_array",    "priority-array — multi-state version"),
    (0x0000, 0x68, 0x21, "FROM_EXCEL", "uint8",             "relinquish-default — default state index"),
    (0x0000, 0x6E, 0x75, "FROM_EXCEL", "string",            "state-text — first state name (e.g. 'Occupied')"),
    (0x0000, 0x71, 0x21, "FIXED",      "uint8",             "status-flags — 0x00"),
    # --- Context 0x0001: Alarm/event ---
    (0x0001, 0x60, 0x75, "FIXED",      "string_triple",     "event-texts — 'Change of State'/'%s Fault'/'Change of State'"),
    (0x0001, 0x61, 0x11, "FIXED",      "bool",              "event-detection-enable — TRUE"),
    (0x0001, 0x62, 0x10, "FIXED",      "bool",              "event-enable — FALSE"),
    (0x0001, 0x63, 0x0c, "FIXED",      "objid_plus",        "notif-class-ref — 0xFFFFFFFF + tail"),
    (0x0001, 0x64, 0x21, "FIXED",      "uint8",             "notify-type — 0x00"),
    # --- Context 0x0004: Vendor-specific ---
    (0x0004, 0x56, 0x10, "FIXED",      "bool",              "vendor 0x0456 — FALSE"),
    # --- Context 0x0100: Terminal ---
    (0x0100, 0x09, 0x91, "COMPUTED",   "uint8",             "terminal ref"),
]


# ============================================================
# NOTIF_CLS — Notification Class (type 26)
# ============================================================
# Source: RC Studio VVT-BYP-ISV000E.pan, NOTIF inst=1,2

NOTIF_CLS_PROPERTIES = [
    # --- Context 0x0000: Standard ---
    (0x0000, 0x1C, 0x71, "FIXED",      "enum",              "description — 0x00 (null)"),
    (0x0000, 0x4D, 0x75, "FROM_EXCEL", "mu_header",         "Mu object name"),
    (0x0000, 0x51, 0x10, "FIXED",      "bool",              "out-of-service — FALSE"),
    # --- Context 0x0004: Vendor-specific ---
    (0x0004, 0x26, 0x09, "COMPUTED",   "notif_config",      "notification config — complex schedule data"),
    (0x0004, 0x27, 0x75, "FROM_EXCEL", "string",            "notification group name"),
]


# ============================================================
# SYS_GROUP — System Group (type 141)
# ============================================================
# Source: RC Studio VVT-BYP-ISV000E.pan, SYS_GROUP inst=1

SYS_GROUP_PROPERTIES = [
    # --- Context 0x0000: Standard ---
    (0x0000, 0x1C, 0x71, "FIXED",      "enum",              "description — 0x00 (null)"),
    (0x0000, 0x4D, 0x75, "FROM_EXCEL", "mu_header",         "Mu object name — {device-name}-PAGE"),
    (0x0000, 0x75, 0x91, "FIXED",      "uint8",             "units — 0x3A (58)"),
    # --- Context 0x0004: Vendor-specific ---
    (0x0004, 0x28, 0x09, "COMPUTED",   "grid_data",         "grid layout — point refs for graphic page"),
    (0x0004, 0x4A, 0x91, "FIXED",      "uint8",             "vendor 0x044A — 0x05"),
]


# ============================================================
# NC_GROUP — Network/System Group (type 15)
# ============================================================
# Source: blank MACH-ProAir/Pro1/ProZone .panx files
# NOTE: Varies significantly by controller family

NC_GROUP_PROPERTIES = [
    # MACH-Pro family (simple, 7 bytes pre-Mu):
    # --- Context 0x0000: Standard ---
    (0x0000, 0x4D, 0x75, "FROM_EXCEL", "mu_header",         "Mu object name — 'System', 'General', or 'Trend'"),
    # NOTE: Pre-Mu is 7 bytes for MACH-Pro: 00 00 00 [0D|0E] 00 00 00
    #       0x0D for inst=0,1 (System/General), 0x0E for inst=65 (Trend)
    # FLEXair has much more complex NC_GROUP with status refs
]


# ============================================================
# MO — Multi-Output (type 14)
# ============================================================
# Source: blank MACH-ProAir-18.panx, MO inst=7

MO_PROPERTIES = [
    # --- Context 0x0000: Standard ---
    (0x0000, 0x11, 0x21, "FIXED",      "uint8",             "polarity — 0x01"),
    (0x0000, 0x1C, 0x75, "FROM_EXCEL", "string",            "description — e.g. 'Damper Control'"),
    (0x0000, 0x23, 0x82, "FIXED",      "obj_ref",           "system-group-ref — 0x050000"),
    (0x0000, 0x28, 0x21, "FIXED",      "uint8",             "feedback-ref — 0x01"),
    (0x0000, 0x4D, 0x75, "FROM_EXCEL", "mu_header",         "Mu object name — {device-name}-POINTNAME"),
    (0x0000, 0x51, 0x10, "FIXED",      "bool",              "out-of-service — FALSE"),
    (0x0000, 0x55, 0x21, "FIXED",      "uint8",             "present-value — 0x03"),
    (0x0000, 0x57, 0x00, "FIXED",      "priority_array",    "priority-array — multi-output version"),
    (0x0000, 0x68, 0x21, "FIXED",      "uint8",             "relinquish-default — 0x01"),
    (0x0000, 0x6E, 0x75, "FIXED",      "string",            "state-text — 'Close'"),
    (0x0000, 0x71, 0x21, "FIXED",      "uint8",             "status-flags — 0x00"),
    # --- Context 0x0001: Alarm/event ---
    (0x0001, 0x60, 0x75, "FIXED",      "string_triple",     "event-texts — 'Command Failure'/..."),
    (0x0001, 0x61, 0x11, "FIXED",      "bool",              "event-detection-enable — TRUE"),
    (0x0001, 0x62, 0x10, "FIXED",      "bool",              "event-enable — FALSE"),
    (0x0001, 0x63, 0x0c, "FIXED",      "objid_plus",        "notif-class-ref — 0xFFFFFFFF + tail"),
    (0x0001, 0x64, 0x21, "FIXED",      "uint8",             "notify-type — 0x00"),
    # --- Context 0x0004: Vendor-specific ---
    (0x0004, 0x1E, 0x11, "FIXED",      "bool",              "vendor 0x041E — TRUE"),
    # --- Context 0x0100: Terminal ---
    (0x0100, 0x09, 0x91, "COMPUTED",   "uint8",             "terminal ref"),
]


# ============================================================
# DEVICE — Device Object (type 8)
# ============================================================
# Source: blank .panx files (all 46 models)
# NOTE: Contains controller model string and serial number
#       Varies by model — serial is per-device

DEVICE_PROPERTIES = [
    # Pre-Mu data (no Mu header in most blanks):
    # [00 00 00 08 00 00 00] then controller-specific data
    # Contains: 0x4D71 marker (not 0x4D75 Mu), model string, firmware version
    # Vendor props vary heavily by controller family
    "NEEDS_REVIEW",  # Complex per-model structure — will template from blanks directly
]


# ============================================================
# NOTIF2 — Notification Class 2 / Event Enrollment (type 27)
# ============================================================
# Source: RC Studio VVT-BYP-ISV000E.pan, type 27 inst=1

NOTIF2_PROPERTIES = [
    # --- Context 0x0000: Standard ---
    (0x0000, 0x11, 0x21, "FIXED",      "uint8",             "polarity — 0x41"),
    (0x0000, 0x1C, 0x71, "FIXED",      "enum",              "description — 0x00 (null)"),
    (0x0000, 0x23, 0x82, "FIXED",      "obj_ref",           "system-group-ref — 0x050000"),
    (0x0000, 0x48, 0x91, "FIXED",      "uint8",             "notification-class — 0x01"),
    (0x0000, 0x4D, 0x75, "FROM_EXCEL", "mu_header",         "Mu object name"),
    (0x0000, 0x7E, 0x22, "FIXED",      "uint16_be",         "record-count — 0x0200"),
    (0x0000, 0x84, 0x0c, "FROM_EXCEL", "objid_be32",        "monitored-object-ref — ObjID of monitored point"),
    (0x0000, 0x85, 0x10, "FIXED",      "bool",              "event-enable — FALSE"),
    (0x0000, 0x86, 0x23, "FIXED",      "special",           "acked-transitions — 0x015F9000"),
    (0x0000, 0x89, 0x21, "FIXED",      "uint8",             "event-type — 0x40"),
    (0x0000, 0x8E, 0xa4, "FIXED",      "event_timestamps",  "event-timestamps — a4 FFFFFFFF b4 FFFFFFFF 00"),
    (0x0000, 0x90, 0x10, "FIXED",      "bool",              "notify-type — FALSE"),
    (0x0000, 0xC5, 0x91, "FIXED",      "uint8",             "vendor 0xC5 — 0x00"),
    # --- Context 0x0001: Alarm/event ---
    (0x0001, 0x60, 0x71, "FIXED",      "enum",              "event-msg-texts — 0x00 (null)"),
    (0x0001, 0x61, 0x11, "FIXED",      "bool",              "event-detection-enable — TRUE"),
    (0x0001, 0x63, 0x0c, "FIXED",      "objid_plus",        "notif-class-ref — 0xFFFFFFFF"),
    # --- Context 0x0100: Terminal ---
    (0x0100, 0x09, 0x91, "COMPUTED",   "uint8",             "terminal ref"),
]


# ============================================================
# T128 — Unknown/Log Object (type 128)
# ============================================================
# Source: blank RC-FLEXone .panx files
# Contains firmware log messages — likely auto-generated by controller
# Not needed for SBS compilation

T128_PROPERTIES = "SKIP"  # Firmware log — auto-generated, not user-configurable


# ============================================================
# T134 — Flow Tool (type 134)
# ============================================================
# Source: blank MACH-ProAir .panx files, FLEXair blanks
# Flow measurement tool configuration — ProAir/FLEXair specific

T134_PROPERTIES = "NEEDS_REVIEW"  # ProAir/FLEXair flow tool — controller-specific


# ============================================================
# T145 — Unknown (type 145)
# ============================================================
# Source: blank MACH-ProView LCD .panx files
# ProView LCD specific — minimal data (2-9 bytes)

T145_PROPERTIES = "SKIP"  # ProView LCD specific — not in scope


# ============================================================
# T149 — Unknown (type 149)
# ============================================================
# Source: blank MACH-ProView LCD .panx files
# ProView LCD specific — display/UI object

T149_PROPERTIES = "SKIP"  # ProView LCD specific — not in scope


# ============================================================
# T151 — Unknown (type 151)
# ============================================================
# Source: blank MACH-ProView LCD .panx files

T151_PROPERTIES = "SKIP"  # ProView LCD specific — not in scope


# ============================================================
# T153 — Unknown (type 153)
# ============================================================
# Source: blank MACH-ProView LCD .panx files

T153_PROPERTIES = "SKIP"  # ProView LCD specific — not in scope
