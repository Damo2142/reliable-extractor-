"""
SBS Composition Engine v2 — Module Registry

Central registry of all available modules. Builds and caches module instances.
"""

from composition.modules import (
    core, fan_supply, fan_return_exhaust, heating, cooling,
    economizer, erw, ventilation, optimum_start, safety, preheat, humidity, pump,
    dual_duct
)
from composition.modules.hw_plant import (
    build_core as hwp_build_core,
    build_blr_cascade, build_blr_full,
    build_pump_cs as hwp_build_pump_cs,
    build_pump_vfd as hwp_build_pump_vfd,
    build_pump_pri_sec as hwp_build_pump_pri_sec,
    build_mixing_valve, build_iso_valves, build_comb_damper,
    build_heat_exchanger, build_ahu_integration, build_makeup_water
)


# Registry: module_id -> builder function
_BUILDERS = {}


def _register(module_id, builder_fn):
    _BUILDERS[module_id] = builder_fn


# Core
_register("core", core.build)

# Supply fan
_register("fan-sf-vfd", fan_supply.build_sf_vfd)
_register("fan-sf-cs", fan_supply.build_sf_cs)
_register("fan-sf-ecm", fan_supply.build_sf_ecm)

# Return / exhaust / relief fan
_register("fan-rf-vfd", fan_return_exhaust.build_rf_vfd)
_register("fan-rf-cs", fan_return_exhaust.build_rf_cs)
_register("fan-ef-vfd", fan_return_exhaust.build_ef_vfd)
_register("fan-ef-cs", fan_return_exhaust.build_ef_cs)
_register("fan-rlf-vfd", fan_return_exhaust.build_rlf_vfd)
_register("fan-rlf-cs", fan_return_exhaust.build_rlf_cs)

# Heating
_register("htg-hw", heating.build_htg_hw)
_register("htg-elec", heating.build_htg_elec)
_register("htg-elec-2", heating.build_htg_elec_2)
_register("htg-elec-3", heating.build_htg_elec_3)
_register("htg-elec-scr", heating.build_htg_elec_scr)
_register("htg-gas", heating.build_htg_gas)
_register("htg-gas-mod", heating.build_htg_gas_mod)

# Cooling
_register("clg-chw", cooling.build_clg_chw)
_register("clg-dx", cooling.build_clg_dx)
_register("clg-dx-2", cooling.build_clg_dx_2)
_register("clg-dx-vfd", cooling.build_clg_dx_vfd)

# Economizer
_register("econ-db", economizer.build_econ_db)
_register("econ-enth", economizer.build_econ_enth)
_register("econ-diff", economizer.build_econ_diff)
_register("econ-diff-db", economizer.build_econ_diff_db)

# Energy Recovery
_register("erw", erw.build)

# Ventilation
_register("vent-fix", ventilation.build_vent_fix)
_register("vent-ams", ventilation.build_vent_ams)
_register("dcv-co2", ventilation.build_dcv_co2)
_register("dcv-occ", ventilation.build_dcv_occ)
_register("vent-100", ventilation.build_vent_100)

# Optimum Start
_register("opt-start", optimum_start.build)

# Safety
_register("safe-freeze", safety.build_safe_freeze)
_register("safe-smoke", safety.build_safe_smoke)
_register("safe-hi-static", safety.build_safe_hi_static)
_register("safe-filter", safety.build_safe_filter)
_register("safe-filter-oa", safety.build_safe_filter_oa)
_register("safe-filter-final", safety.build_safe_filter_final)
_register("safe-filter-ea", safety.build_safe_filter_ea)
_register("safe-fire-sd", safety.build_safe_fire_sd)
_register("safe-cond-ovf", safety.build_safe_cond_ovf)
_register("safe-freeze-dp", safety.build_safe_freeze_dp)
_register("safe-ea-static", safety.build_safe_ea_static)
_register("safe-ra-static", safety.build_safe_ra_static)

# Preheat
_register("ph-hw", preheat.build_ph_hw)
_register("ph-elec", preheat.build_ph_elec)
_register("ph-glycol", preheat.build_ph_glycol)

# Humidity
_register("hum-stm", humidity.build_hum_stm)
_register("hum-elec", humidity.build_hum_elec)
_register("hum-ultra", humidity.build_hum_ultra)
_register("dehum-sc", humidity.build_dehum_sc)

# Pumps
_register("htg-hw-pump", pump.build_hw_pump)
_register("clg-chw-pump", pump.build_chw_pump)
_register("ph-hw-pump", pump.build_ph_pump)

# Dual Duct
_register("dd-cold-chw", dual_duct.build_dd_cold_chw)
_register("dd-hot-hw", dual_duct.build_dd_hot_hw)
_register("dd-hot-elec", dual_duct.build_dd_hot_elec)

# HW Plant — static core registration (dynamic modules built via hwp_assemble)
_register("hw-core", hwp_build_core)


# Cache built modules
_CACHE = {}


def get_module(module_id):
    """Get a module by ID. Builds on first access."""
    if module_id not in _CACHE:
        if module_id not in _BUILDERS:
            raise ValueError(f"Unknown module: {module_id}")
        _CACHE[module_id] = _BUILDERS[module_id]()
    return _CACHE[module_id]


def list_modules():
    """List all available module IDs."""
    return sorted(_BUILDERS.keys())


def list_by_category():
    """List modules grouped by category."""
    result = {}
    for mid in _BUILDERS:
        mod = get_module(mid)
        cat = mod.category
        if cat not in result:
            result[cat] = []
        result[cat].append({
            "id": mod.id,
            "name": mod.name,
            "description": mod.description,
            "is_core": mod.is_core,
            "mutually_exclusive_group": mod.mutually_exclusive_group,
        })
    return result


def get_core_modules():
    """Get all modules marked as core (always included)."""
    return [mid for mid in _BUILDERS if get_module(mid).is_core]


# ═══════════════════════════════════════════════════════════════════════════
# SBS Standard Equipment Configurations
#
# Organized by equipment family, then least to most complex.
# Pick a standard, then toggle modules on/off to customize.
#
# Numbering:
#   VAV AHU:     SBS-AHU-101 to 120
#   CV AHU:      SBS-AHU-201 to 220
#   RTU:         SBS-RTU-301 to 320
#   DOAS / MAU:  SBS-DOAS-401 to 420
#   (Future)
#   VAV Terminal: SBS-VAV-501 to 520
#   FCU:         SBS-FCU-601 to 620
#   Plant:       SBS-PLT-701 to 720
# ═══════════════════════════════════════════════════════════════════════════

# Base safety modules
_SAFETY_BASE = ["safe-freeze", "safe-smoke", "safe-filter"]
_SAFETY_FULL = ["safe-freeze", "safe-smoke", "safe-hi-static", "safe-filter",
                "safe-filter-oa", "safe-filter-final"]
_SAFETY_FULL_EA = _SAFETY_FULL + ["safe-filter-ea"]

# Equipment family definitions — drives the UI dropdowns
EQUIPMENT_FAMILIES = {
    "VAV-AHU": {
        "name": "VAV Air Handling Unit",
        "description": "Variable air volume AHU — VFD supply fan, duct static pressure control, serves VAV terminal units",
        "prefix": "SBS-AHU",
        "required_modules": ["core", "fan-sf-vfd", "opt-start"],
        "available_categories": ["cooling", "heating", "preheat", "economizer", "energy-recovery",
                                 "ventilation", "humidity", "fan", "safety", "pump"],
        "notes": "Supply fan always VFD. Return/exhaust/relief fan optional.",
    },
    "CV-AHU": {
        "name": "Constant Volume AHU",
        "description": "Constant volume AHU — constant speed or 2-speed fan, SAT control, no duct static",
        "prefix": "SBS-AHU",
        "required_modules": ["core"],
        "available_categories": ["cooling", "heating", "preheat", "economizer", "energy-recovery",
                                 "ventilation", "humidity", "fan", "safety", "pump"],
        "notes": "Fan is constant speed or 2-speed. No DSP loop. SAT reset only.",
    },
    "RTU": {
        "name": "Rooftop Unit (Packaged)",
        "description": "Packaged rooftop unit — DX cooling, electric or gas heat, factory assembled",
        "prefix": "SBS-RTU",
        "required_modules": ["core"],
        "available_categories": ["cooling", "heating", "economizer", "ventilation", "safety"],
        "notes": "DX cooling (staged or VFD). Electric or gas heat. Usually no preheat or ERW.",
    },
    "DOAS": {
        "name": "Dedicated Outdoor Air System",
        "description": "100% outside air unit — no return air, typically with energy recovery",
        "prefix": "SBS-DOAS",
        "required_modules": ["core", "fan-sf-vfd", "vent-100"],
        "available_categories": ["cooling", "heating", "preheat", "energy-recovery", "humidity", "safety", "pump"],
        "notes": "Always 100% OA. No economizer (no return air). ERW strongly recommended.",
    },
    "SZ-CV": {
        "name": "Single Zone Constant Volume",
        "description": "Constant speed fan, space temperature control — serves one zone, heating/cooling cycles to maintain space temp",
        "prefix": "SBS-SZCV",
        "required_modules": ["core"],
        "available_categories": ["cooling", "heating", "preheat", "economizer", "energy-recovery",
                                 "ventilation", "humidity", "safety"],
        "notes": "Fan is constant speed. No duct static loop. Space temp sensor drives heating/cooling. Single zone only.",
    },
    "SZ-VAV": {
        "name": "Single Zone VAV",
        "description": "VFD fan modulates to space temperature — no VAV boxes, fan speed = capacity control for single zone",
        "prefix": "SBS-SZVAV",
        "required_modules": ["core", "fan-sf-vfd"],
        "available_categories": ["cooling", "heating", "preheat", "economizer", "energy-recovery",
                                 "ventilation", "humidity", "safety", "pump"],
        "notes": "VFD supply fan modulates to space temp (NOT duct static). No downstream VAV boxes. Single zone served.",
    },
    "DD-AHU": {
        "name": "Dual Duct AHU",
        "description": "Hot deck + cold deck — downstream dual-duct mixing boxes blend hot and cold air per zone",
        "prefix": "SBS-DD",
        "required_modules": ["core"],
        "available_categories": ["cooling", "heating", "preheat", "economizer", "energy-recovery",
                                 "ventilation", "humidity", "fan", "safety", "pump"],
        "notes": "Two parallel decks with independent SAT control. Hot deck SAT reset from heating demand, cold deck SAT reset from cooling demand. Common in retrofit.",
    },
    "MZ-AHU": {
        "name": "Multizone AHU",
        "description": "Zone mixing dampers AT the unit — hot and cold decks with per-zone mixing at the AHU",
        "prefix": "SBS-MZ",
        "required_modules": ["core"],
        "available_categories": ["cooling", "heating", "preheat", "economizer", "energy-recovery",
                                 "ventilation", "safety"],
        "notes": "Zone dampers are outputs on the AHU controller. Limited zone count (4-12 typical). Hot/cold deck SAT control. Common in older buildings / retrofit.",
    },
    "HW-PLANT": {
        "name": "Hot Water Plant",
        "description": "Central HW heating plant — boiler control, pump control, distribution. MPS controller.",
        "prefix": "SBS-PLT",
        "required_modules": ["hw-core"],
        "available_categories": ["hw-core", "hw-boiler", "hw-pump", "hw-optional"],
        "notes": "Wizard-based configuration. Boiler and pump modules selected via question flow. One controller per plant.",
        "wizard": True,
    },
}

STANDARD_CONFIGS = {
    # ═══════════════════════════════════════════════════════════════════════
    #  VAV AHU — SBS-AHU-101 to 120
    #  Supply fan always VFD. Duct static pressure control standard.
    # ═══════════════════════════════════════════════════════════════════════

    "SBS-AHU-101": {
        "family": "VAV-AHU",
        "name": "CHW / No Heat / Econ-DB",
        "description": "Simplest VAV AHU: CHW cooling only, dry bulb economizer, no heating",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-chw", "econ-db",
            "vent-fix", "opt-start",
        ] + _SAFETY_BASE,
    },
    "SBS-AHU-102": {
        "family": "VAV-AHU",
        "name": "CHW / Electric-2 / Econ-DB",
        "description": "CHW cooling with 2-stage electric backup heat",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-chw", "htg-elec-2", "econ-db",
            "vent-fix", "opt-start",
        ] + _SAFETY_BASE,
    },
    "SBS-AHU-103": {
        "family": "VAV-AHU",
        "name": "CHW / HW / Econ-DB",
        "description": "Standard CHW/HW AHU with dry bulb economizer",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-chw", "htg-hw", "econ-db",
            "vent-fix", "opt-start",
        ] + _SAFETY_BASE,
    },
    "SBS-AHU-104": {
        "family": "VAV-AHU",
        "name": "CHW / HW / Econ-Enth",
        "description": "Standard CHW/HW AHU with enthalpy economizer",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-chw", "htg-hw", "econ-enth",
            "vent-fix", "opt-start",
        ] + _SAFETY_BASE,
    },
    "SBS-AHU-105": {
        "family": "VAV-AHU",
        "name": "CHW / HW / Econ-Enth / RF-VFD",
        "description": "CHW/HW with return fan VFD for building pressure control",
        "modules": [
            "core", "fan-sf-vfd", "fan-rf-vfd",
            "clg-chw", "htg-hw", "econ-enth",
            "vent-fix", "opt-start",
        ] + _SAFETY_FULL,
    },
    "SBS-AHU-106": {
        "family": "VAV-AHU",
        "name": "CHW / HW / Econ-Enth / EF-VFD",
        "description": "CHW/HW with exhaust fan VFD tracking OA airflow",
        "modules": [
            "core", "fan-sf-vfd", "fan-ef-vfd",
            "clg-chw", "htg-hw", "econ-enth",
            "vent-ams", "opt-start",
        ] + _SAFETY_FULL_EA,
    },
    "SBS-AHU-107": {
        "family": "VAV-AHU",
        "name": "CHW / HW / Econ-Enth / ERW",
        "description": "CHW/HW with energy recovery wheel",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-chw", "htg-hw", "econ-enth", "erw",
            "vent-fix", "opt-start",
        ] + _SAFETY_FULL,
    },
    "SBS-AHU-108": {
        "family": "VAV-AHU",
        "name": "CHW / HW / Econ-Enth / ERW / EF-VFD",
        "description": "CHW/HW with ERW + exhaust fan VFD + OA airflow measurement",
        "modules": [
            "core", "fan-sf-vfd", "fan-ef-vfd",
            "clg-chw", "htg-hw", "econ-enth", "erw",
            "vent-ams", "opt-start",
        ] + _SAFETY_FULL_EA,
    },
    "SBS-AHU-109": {
        "family": "VAV-AHU",
        "name": "CHW / HW / Econ-Enth / ERW / EF-VFD / DCV-CO2",
        "description": "Full-featured VAV AHU — the A201 reference config",
        "modules": [
            "core", "fan-sf-vfd", "fan-ef-vfd",
            "clg-chw", "htg-hw", "econ-enth", "erw",
            "dcv-co2", "opt-start",
        ] + _SAFETY_FULL_EA,
    },
    "SBS-AHU-110": {
        "family": "VAV-AHU",
        "name": "CHW / HW / PH-HW / Econ-Enth",
        "description": "CHW/HW with hot water preheat coil + pump",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-chw", "htg-hw", "ph-hw", "econ-enth",
            "vent-fix", "opt-start",
        ] + _SAFETY_FULL,
    },
    "SBS-AHU-111": {
        "family": "VAV-AHU",
        "name": "CHW / HW / PH-HW / Econ-Enth / ERW / EF-VFD",
        "description": "Full preheat config: CHW, HW, preheat, ERW, exhaust fan",
        "modules": [
            "core", "fan-sf-vfd", "fan-ef-vfd",
            "clg-chw", "htg-hw", "ph-hw", "econ-enth", "erw",
            "vent-ams", "opt-start",
        ] + _SAFETY_FULL_EA,
    },
    "SBS-AHU-112": {
        "family": "VAV-AHU",
        "name": "CHW / HW / Econ-Enth / HUM-STM",
        "description": "CHW/HW with steam humidifier",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-chw", "htg-hw", "econ-enth", "hum-stm",
            "vent-fix", "opt-start",
        ] + _SAFETY_FULL,
    },
    "SBS-AHU-113": {
        "family": "VAV-AHU",
        "name": "CHW / HW / Econ-Enth / DEHUM-SC",
        "description": "CHW/HW with subcooling dehumidification",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-chw", "htg-hw", "econ-enth", "dehum-sc",
            "vent-fix", "opt-start",
        ] + _SAFETY_FULL,
    },
    "SBS-AHU-114": {
        "family": "VAV-AHU",
        "name": "FULL — CHW / HW / PH-HW / ERW / EF-VFD / DCV / HUM / DEHUM",
        "description": "Maximum VAV AHU: every feature enabled",
        "modules": [
            "core", "fan-sf-vfd", "fan-ef-vfd",
            "clg-chw", "htg-hw", "ph-hw",
            "econ-enth", "erw",
            "dcv-co2", "hum-stm", "dehum-sc",
            "opt-start",
        ] + _SAFETY_FULL_EA + ["safe-cond-ovf"],
    },

    # ═══════════════════════════════════════════════════════════════════════
    #  RTU (PACKAGED ROOFTOP) — SBS-RTU-301 to 310
    #  DX cooling, electric or gas heat, factory assembled
    # ═══════════════════════════════════════════════════════════════════════

    "SBS-RTU-301": {
        "family": "RTU",
        "name": "DX-1 / Electric-1 / CS — Minimal",
        "description": "Simplest RTU: single DX, single electric, constant speed, no economizer",
        "modules": [
            "core", "fan-sf-cs",
            "clg-dx", "htg-elec",
            "vent-fix",
        ] + _SAFETY_BASE,
    },
    "SBS-RTU-302": {
        "family": "RTU",
        "name": "DX-2 / Electric-2 / VFD / Econ-DB",
        "description": "Standard RTU: 2-stage DX, 2-stage electric, VFD, dry bulb economizer",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-dx-2", "htg-elec-2", "econ-db",
            "vent-fix", "opt-start",
        ] + _SAFETY_BASE,
    },
    "SBS-RTU-303": {
        "family": "RTU",
        "name": "DX-2 / Gas-1 / VFD / Econ-DB",
        "description": "Gas-fired RTU: 2-stage DX, single gas, VFD, economizer",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-dx-2", "htg-gas", "econ-db",
            "vent-fix", "opt-start",
        ] + _SAFETY_BASE,
    },
    "SBS-RTU-304": {
        "family": "RTU",
        "name": "DX-2 / Gas-MOD / VFD / Econ-DB",
        "description": "Modulating gas RTU: 2-stage DX, modulating gas heat",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-dx-2", "htg-gas-mod", "econ-db",
            "vent-fix", "opt-start",
        ] + _SAFETY_BASE,
    },
    "SBS-RTU-305": {
        "family": "RTU",
        "name": "DX-VFD / Electric-SCR / VFD / Econ-DB",
        "description": "Variable capacity RTU: VFD compressor, modulating electric heat",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-dx-vfd", "htg-elec-scr", "econ-db",
            "vent-fix", "opt-start",
        ] + _SAFETY_BASE,
    },
    "SBS-RTU-306": {
        "family": "RTU",
        "name": "DX-2 / Electric-3 / VFD / Econ-DB / DCV-CO2",
        "description": "Full RTU: 2-stage DX, 3-stage electric, VFD, economizer, DCV",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-dx-2", "htg-elec-3", "econ-db",
            "dcv-co2", "opt-start",
        ] + _SAFETY_BASE,
    },

    # ═══════════════════════════════════════════════════════════════════════
    #  CV AHU (CONSTANT VOLUME) — SBS-AHU-201 to 210
    #  Constant speed fan, no duct static, SAT control
    # ═══════════════════════════════════════════════════════════════════════

    "SBS-AHU-201": {
        "family": "CV-AHU",
        "name": "CHW / HW / CS / Econ-DB",
        "description": "Constant volume CHW/HW AHU with dry bulb economizer",
        "modules": [
            "core", "fan-sf-cs",
            "clg-chw", "htg-hw", "econ-db",
            "vent-fix", "opt-start",
        ] + _SAFETY_BASE,
    },
    "SBS-AHU-202": {
        "family": "CV-AHU",
        "name": "CHW / HW / CS / Econ-Enth",
        "description": "Constant volume CHW/HW AHU with enthalpy economizer",
        "modules": [
            "core", "fan-sf-cs",
            "clg-chw", "htg-hw", "econ-enth",
            "vent-fix", "opt-start",
        ] + _SAFETY_BASE,
    },
    "SBS-AHU-203": {
        "family": "CV-AHU",
        "name": "CHW / HW / CS / Econ-Enth / ERW",
        "description": "Constant volume with energy recovery wheel",
        "modules": [
            "core", "fan-sf-cs",
            "clg-chw", "htg-hw", "econ-enth", "erw",
            "vent-fix", "opt-start",
        ] + _SAFETY_FULL,
    },
    "SBS-AHU-204": {
        "family": "CV-AHU",
        "name": "CHW / Electric-2 / CS / Econ-DB",
        "description": "Constant volume CHW + electric heat",
        "modules": [
            "core", "fan-sf-cs",
            "clg-chw", "htg-elec-2", "econ-db",
            "vent-fix", "opt-start",
        ] + _SAFETY_BASE,
    },

    # ═══════════════════════════════════════════════════════════════════════
    #  DOAS / MAU — SBS-DOAS-401 to 410
    #  100% outside air, no return, typically with energy recovery
    # ═══════════════════════════════════════════════════════════════════════

    "SBS-DOAS-401": {
        "family": "DOAS",
        "name": "CHW / PH-HW / ERW",
        "description": "Standard DOAS: CHW cooling, HW preheat, energy recovery wheel",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-chw", "ph-hw", "erw",
            "vent-100",
        ] + _SAFETY_FULL,
    },
    "SBS-DOAS-402": {
        "family": "DOAS",
        "name": "DX-2 / PH-HW / ERW",
        "description": "DX DOAS: 2-stage DX, HW preheat, energy recovery wheel",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-dx-2", "ph-hw", "erw",
            "vent-100",
        ] + _SAFETY_FULL,
    },
    "SBS-DOAS-403": {
        "family": "DOAS",
        "name": "CHW / PH-HW / ERW / HUM-STM",
        "description": "DOAS with humidifier: CHW, HW preheat, ERW, steam humidifier",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-chw", "ph-hw", "erw", "hum-stm",
            "vent-100",
        ] + _SAFETY_FULL,
    },
    "SBS-DOAS-404": {
        "family": "DOAS",
        "name": "CHW / PH-Glycol / ERW",
        "description": "DOAS with glycol preheat: CHW cooling, glycol preheat, ERW",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-chw", "ph-glycol", "erw",
            "vent-100",
        ] + _SAFETY_FULL,
    },
    "SBS-DOAS-405": {
        "family": "DOAS",
        "name": "CHW / HW / No ERW",
        "description": "Simple DOAS without energy recovery: CHW, HW, no ERW",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-chw", "htg-hw",
            "vent-100",
        ] + _SAFETY_BASE,
    },

    # ═══════════════════════════════════════════════════════════════════════
    #  SINGLE ZONE CV — SBS-SZCV-501 to 510
    #  Constant speed fan, space temp control, single zone
    #  Fan cycles or runs continuous — heating/cooling modulates to space temp
    # ═══════════════════════════════════════════════════════════════════════

    "SBS-SZCV-501": {
        "family": "SZ-CV",
        "name": "CHW / HW / CS / Econ-DB — Basic",
        "description": "Single zone CV: CHW cooling, HW heating, constant speed, dry bulb econ",
        "modules": [
            "core", "fan-sf-cs",
            "clg-chw", "htg-hw", "econ-db",
            "vent-fix",
        ] + _SAFETY_BASE,
    },
    "SBS-SZCV-502": {
        "family": "SZ-CV",
        "name": "CHW / Electric-1 / CS — Minimal",
        "description": "Simplest single zone: CHW cooling, single electric heat, constant speed",
        "modules": [
            "core", "fan-sf-cs",
            "clg-chw", "htg-elec",
            "vent-fix",
        ] + _SAFETY_BASE,
    },
    "SBS-SZCV-503": {
        "family": "SZ-CV",
        "name": "DX-1 / Electric-1 / CS — Package",
        "description": "Packaged single zone: single DX, single electric, constant speed",
        "modules": [
            "core", "fan-sf-cs",
            "clg-dx", "htg-elec",
            "vent-fix",
        ] + _SAFETY_BASE,
    },
    "SBS-SZCV-504": {
        "family": "SZ-CV",
        "name": "DX-2 / Gas-1 / CS / Econ-DB — Gas Package",
        "description": "Packaged single zone: 2-stage DX, gas heat, economizer",
        "modules": [
            "core", "fan-sf-cs",
            "clg-dx-2", "htg-gas", "econ-db",
            "vent-fix",
        ] + _SAFETY_BASE,
    },
    "SBS-SZCV-505": {
        "family": "SZ-CV",
        "name": "CHW / HW / CS / Econ-Enth / ERW — With ERW",
        "description": "Single zone CV with energy recovery wheel",
        "modules": [
            "core", "fan-sf-cs",
            "clg-chw", "htg-hw", "econ-enth", "erw",
            "vent-fix",
        ] + _SAFETY_FULL,
    },
    "SBS-SZCV-506": {
        "family": "SZ-CV",
        "name": "HW Only / CS — Heating Only (MAU)",
        "description": "Heating-only make-up air: HW heat, constant speed, no cooling",
        "modules": [
            "core", "fan-sf-cs",
            "htg-hw",
            "vent-fix",
        ] + _SAFETY_BASE,
    },

    # ═══════════════════════════════════════════════════════════════════════
    #  SINGLE ZONE VAV — SBS-SZVAV-601 to 610
    #  VFD supply fan modulates to SPACE TEMP (not duct static)
    #  No downstream VAV boxes — fan speed IS the capacity control
    # ═══════════════════════════════════════════════════════════════════════

    "SBS-SZVAV-601": {
        "family": "SZ-VAV",
        "name": "CHW / HW / VFD / Econ-DB — Basic",
        "description": "Single zone VAV: CHW/HW, VFD fan to space temp, dry bulb econ",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-chw", "htg-hw", "econ-db",
            "vent-fix", "opt-start",
        ] + _SAFETY_BASE,
    },
    "SBS-SZVAV-602": {
        "family": "SZ-VAV",
        "name": "CHW / HW / VFD / Econ-Enth — Enthalpy",
        "description": "Single zone VAV: CHW/HW, VFD fan to space temp, enthalpy econ",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-chw", "htg-hw", "econ-enth",
            "vent-fix", "opt-start",
        ] + _SAFETY_BASE,
    },
    "SBS-SZVAV-603": {
        "family": "SZ-VAV",
        "name": "CHW / HW / VFD / Econ-Enth / ERW — With ERW",
        "description": "Single zone VAV with energy recovery wheel",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-chw", "htg-hw", "econ-enth", "erw",
            "vent-fix", "opt-start",
        ] + _SAFETY_FULL,
    },
    "SBS-SZVAV-604": {
        "family": "SZ-VAV",
        "name": "DX-2 / Electric-2 / VFD / Econ-DB — Package",
        "description": "Packaged single zone VAV: 2-stage DX, 2-stage electric, VFD to space temp",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-dx-2", "htg-elec-2", "econ-db",
            "vent-fix", "opt-start",
        ] + _SAFETY_BASE,
    },
    "SBS-SZVAV-605": {
        "family": "SZ-VAV",
        "name": "DX-2 / Gas-1 / VFD / Econ-DB — Gas Package",
        "description": "Packaged single zone VAV: 2-stage DX, gas heat, VFD to space temp",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-dx-2", "htg-gas", "econ-db",
            "vent-fix", "opt-start",
        ] + _SAFETY_BASE,
    },
    "SBS-SZVAV-606": {
        "family": "SZ-VAV",
        "name": "CHW / HW / PH-HW / VFD / Econ-Enth / ERW — Full Featured",
        "description": "Full single zone VAV: CHW, HW, preheat, ERW, enthalpy econ",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-chw", "htg-hw", "ph-hw", "econ-enth", "erw",
            "vent-fix", "opt-start",
        ] + _SAFETY_FULL,
    },

    # ═══════════════════════════════════════════════════════════════════════
    #  DUAL DUCT AHU — SBS-DD-701 to 710
    #  Hot deck + cold deck, downstream mixing boxes
    # ═══════════════════════════════════════════════════════════════════════

    "SBS-DD-701": {
        "family": "DD-AHU",
        "name": "DD CHW / HW / VFD / Econ-DB",
        "description": "Dual duct VAV: CHW cold deck, HW hot deck, VFD fan, dry bulb econ",
        "modules": [
            "core", "fan-sf-vfd",
            "dd-cold-chw", "dd-hot-hw", "econ-db",
            "vent-fix", "opt-start",
        ] + _SAFETY_FULL,
    },
    "SBS-DD-702": {
        "family": "DD-AHU",
        "name": "DD CHW / HW / VFD / Econ-Enth",
        "description": "Dual duct VAV: CHW cold deck, HW hot deck, enthalpy econ",
        "modules": [
            "core", "fan-sf-vfd",
            "dd-cold-chw", "dd-hot-hw", "econ-enth",
            "vent-fix", "opt-start",
        ] + _SAFETY_FULL,
    },
    "SBS-DD-703": {
        "family": "DD-AHU",
        "name": "DD CHW / HW / CS / Econ-DB — CV Dual Duct",
        "description": "Dual duct CV: constant speed fan, CHW/HW decks",
        "modules": [
            "core", "fan-sf-cs",
            "dd-cold-chw", "dd-hot-hw", "econ-db",
            "vent-fix", "opt-start",
        ] + _SAFETY_BASE,
    },
    "SBS-DD-704": {
        "family": "DD-AHU",
        "name": "DD CHW / Electric / VFD / Econ-DB",
        "description": "Dual duct VAV: CHW cold deck, electric hot deck",
        "modules": [
            "core", "fan-sf-vfd",
            "dd-cold-chw", "dd-hot-elec", "econ-db",
            "vent-fix", "opt-start",
        ] + _SAFETY_FULL,
    },
    "SBS-DD-705": {
        "family": "DD-AHU",
        "name": "DD CHW / HW / VFD / Econ-Enth / ERW",
        "description": "Dual duct VAV with energy recovery wheel",
        "modules": [
            "core", "fan-sf-vfd",
            "dd-cold-chw", "dd-hot-hw", "econ-enth", "erw",
            "vent-fix", "opt-start",
        ] + _SAFETY_FULL,
    },

    # ═══════════════════════════════════════════════════════════════════════
    #  MULTIZONE AHU — SBS-MZ-801 to 810
    #  Zone mixing dampers at the unit, hot/cold decks
    # ═══════════════════════════════════════════════════════════════════════

    "SBS-MZ-801": {
        "family": "MZ-AHU",
        "name": "MZ CHW / HW / CS / Econ-DB",
        "description": "Multizone CV: CHW cold deck, HW hot deck, constant speed, dry bulb econ",
        "modules": [
            "core", "fan-sf-cs",
            "dd-cold-chw", "dd-hot-hw", "econ-db",
            "vent-fix", "opt-start",
        ] + _SAFETY_BASE,
    },
    "SBS-MZ-802": {
        "family": "MZ-AHU",
        "name": "MZ CHW / HW / CS / Econ-Enth",
        "description": "Multizone CV: CHW cold deck, HW hot deck, enthalpy econ",
        "modules": [
            "core", "fan-sf-cs",
            "dd-cold-chw", "dd-hot-hw", "econ-enth",
            "vent-fix", "opt-start",
        ] + _SAFETY_BASE,
    },
    "SBS-MZ-803": {
        "family": "MZ-AHU",
        "name": "MZ CHW / Electric / CS / Econ-DB",
        "description": "Multizone CV: CHW cold deck, electric hot deck",
        "modules": [
            "core", "fan-sf-cs",
            "dd-cold-chw", "dd-hot-elec", "econ-db",
            "vent-fix", "opt-start",
        ] + _SAFETY_BASE,
    },
    "SBS-MZ-804": {
        "family": "MZ-AHU",
        "name": "MZ CHW / HW / VFD / Econ-DB",
        "description": "Multizone with VFD: CHW/HW decks, dry bulb econ",
        "modules": [
            "core", "fan-sf-vfd",
            "dd-cold-chw", "dd-hot-hw", "econ-db",
            "vent-fix", "opt-start",
        ] + _SAFETY_FULL,
    },

    # ═══════════════════════════════════════════════════════════════════════
    #  HW Plant — SBS-PLT-701 to 720
    #  Wizard-based. Module list built dynamically from parameters.
    #  These presets define the wizard defaults for quick selection.
    # ═══════════════════════════════════════════════════════════════════════
    "SBS-PLT-701": {
        "family": "HW-PLANT",
        "name": "2-Boiler Cascade, 2-Pump CS",
        "description": "Interface boilers with analog setpoint, 2 constant speed pumps",
        "modules": ["hw-core"],
        "hwp_params": {
            "boiler_type": "cascade", "num_boilers": 2, "spt_output": "analog",
            "monitor_boiler_temps": False,
            "pump_type": "cs", "num_pumps": 2,
        },
    },
    "SBS-PLT-702": {
        "family": "HW-PLANT",
        "name": "2-Boiler Cascade, 2-Pump VFD",
        "description": "Interface boilers with analog setpoint, 2 VFD pumps with DP control",
        "modules": ["hw-core"],
        "hwp_params": {
            "boiler_type": "cascade", "num_boilers": 2, "spt_output": "analog",
            "monitor_boiler_temps": False,
            "pump_type": "vfd", "num_pumps": 2,
        },
    },
    "SBS-PLT-703": {
        "family": "HW-PLANT",
        "name": "2-Boiler Full, 2-Pump CS",
        "description": "Direct fire rate control, 2 boilers, 2 constant speed pumps",
        "modules": ["hw-core"],
        "hwp_params": {
            "boiler_type": "full", "num_boilers": 2, "monitor_boiler_temps": True,
            "pump_type": "cs", "num_pumps": 2,
        },
    },
    "SBS-PLT-704": {
        "family": "HW-PLANT",
        "name": "2-Boiler Full, 2-Pump VFD",
        "description": "Direct fire rate control, 2 boilers, 2 VFD pumps with DP",
        "modules": ["hw-core"],
        "hwp_params": {
            "boiler_type": "full", "num_boilers": 2, "monitor_boiler_temps": True,
            "pump_type": "vfd", "num_pumps": 2,
        },
    },
    "SBS-PLT-705": {
        "family": "HW-PLANT",
        "name": "3-Boiler Full, Pri-Sec (2+2)",
        "description": "3 direct-control boilers, primary/secondary pumping 2+2",
        "modules": ["hw-core"],
        "hwp_params": {
            "boiler_type": "full", "num_boilers": 3, "monitor_boiler_temps": True,
            "pump_type": "pri-sec", "num_primary": 2, "num_secondary": 2,
        },
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# HW Plant Dynamic Assembly
# ═══════════════════════════════════════════════════════════════════════════

def hwp_assemble(params):
    """Build HW plant module list from wizard parameters.

    Args:
        params: dict with keys:
            boiler_type: "cascade" | "full"
            num_boilers: 1-4
            spt_output: "analog" | "bacnet" (cascade only)
            monitor_boiler_temps: bool
            pump_type: "cs" | "vfd" | "pri-sec"
            num_pumps: 1-4 (for cs/vfd)
            num_primary: 1-4 (for pri-sec)
            num_secondary: 1-4 (for pri-sec)
            mixing_valve: bool
            iso_valves: bool
            comb_damper: bool
            heat_exchanger: bool
            hx_valve_type: "single_mod" | "single_onoff" | "third_twothird"
            ahu_integration: bool
            num_ahus: 1-8
            makeup_water: bool

    Returns:
        list of Module objects ready for assembly
    """
    modules = [hwp_build_core()]

    bt = params.get('boiler_type', 'cascade')
    nb = params.get('num_boilers', 2)
    mbt = params.get('monitor_boiler_temps', False)

    if bt == 'cascade':
        analog = params.get('spt_output', 'analog') == 'analog'
        modules.append(build_blr_cascade(num_boilers=nb, analog_spt=analog, monitor_hwst=mbt))
    else:
        modules.append(build_blr_full(num_boilers=nb, monitor_hwst=mbt))

    pt = params.get('pump_type', 'cs')
    if pt == 'cs':
        modules.append(hwp_build_pump_cs(num_pumps=params.get('num_pumps', 2)))
    elif pt == 'vfd':
        modules.append(hwp_build_pump_vfd(num_pumps=params.get('num_pumps', 2)))
    elif pt == 'pri-sec':
        modules.append(hwp_build_pump_pri_sec(
            num_primary=params.get('num_primary', 2),
            num_secondary=params.get('num_secondary', 2)))

    if params.get('mixing_valve'):
        modules.append(build_mixing_valve())
    if params.get('iso_valves'):
        modules.append(build_iso_valves(num_boilers=nb))
    if params.get('comb_damper'):
        modules.append(build_comb_damper(num_boilers=nb))
    if params.get('heat_exchanger'):
        hvt = params.get('hx_valve_type', 'single_mod')
        modules.append(build_heat_exchanger(valve_type=hvt))
    if params.get('ahu_integration'):
        modules.append(build_ahu_integration(num_ahus=params.get('num_ahus', 2)))
    if params.get('makeup_water'):
        modules.append(build_makeup_water())

    return modules
