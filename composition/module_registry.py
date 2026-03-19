"""
SBS Composition Engine v2 — Module Registry

Central registry of all available modules. Builds and caches module instances.
"""

from composition.modules import (
    core, fan_supply, fan_return_exhaust, heating, cooling,
    economizer, erw, ventilation, optimum_start, safety, preheat, humidity, pump
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
# SBS Standard AHU Configurations — SBS-AHU-101 through SBS-AHU-120
# Organized from least complex to most complex.
# Pick a standard, then toggle modules on/off to customize.
# ═══════════════════════════════════════════════════════════════════════════

# Base safety modules included in all configs
_SAFETY_BASE = ["safe-freeze", "safe-smoke", "safe-filter"]
_SAFETY_FULL = ["safe-freeze", "safe-smoke", "safe-hi-static", "safe-filter",
                "safe-filter-oa", "safe-filter-final"]
_SAFETY_FULL_EA = _SAFETY_FULL + ["safe-filter-ea"]

STANDARD_CONFIGS = {
    # ── SIMPLE / PACKAGED RTU (101-104) ──────────────────────────────────
    "SBS-AHU-101": {
        "name": "DX-1 / Electric-1 / CS — Minimal RTU",
        "description": "Simplest packaged unit: single DX, single electric heat, constant speed fan, no economizer",
        "modules": [
            "core", "fan-sf-cs",
            "clg-dx", "htg-elec",
            "vent-fix",
        ] + _SAFETY_BASE,
    },
    "SBS-AHU-102": {
        "name": "DX-2 / Electric-2 / VFD / Econ-DB — Standard RTU",
        "description": "Standard packaged RTU: 2-stage DX, 2-stage electric, VFD, dry bulb economizer",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-dx-2", "htg-elec-2", "econ-db",
            "vent-fix", "opt-start",
        ] + _SAFETY_BASE,
    },
    "SBS-AHU-103": {
        "name": "DX-2 / Gas-1 / VFD / Econ-DB — Gas RTU",
        "description": "Gas-fired packaged RTU: 2-stage DX, single gas, VFD, dry bulb economizer",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-dx-2", "htg-gas", "econ-db",
            "vent-fix", "opt-start",
        ] + _SAFETY_BASE,
    },
    "SBS-AHU-104": {
        "name": "DX-VFD / Electric-SCR / VFD / Econ-DB — Variable RTU",
        "description": "Variable capacity RTU: VFD compressor, modulating electric heat, VFD fan",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-dx-vfd", "htg-elec-scr", "econ-db",
            "vent-fix", "opt-start",
        ] + _SAFETY_BASE,
    },

    # ── CHW COOLING / NO HEATING (105-106) ───────────────────────────────
    "SBS-AHU-105": {
        "name": "CHW / No Heat / VFD / Econ-DB — Cooling Only",
        "description": "Cooling-only AHU: CHW coil, VFD fan, dry bulb economizer, no heating",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-chw", "econ-db",
            "vent-fix", "opt-start",
        ] + _SAFETY_BASE,
    },
    "SBS-AHU-106": {
        "name": "CHW / Electric-2 / VFD / Econ-DB — CHW + Electric",
        "description": "CHW cooling with electric backup heat, VFD fan, economizer",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-chw", "htg-elec-2", "econ-db",
            "vent-fix", "opt-start",
        ] + _SAFETY_BASE,
    },

    # ── CHW / HW STANDARD (107-110) ─────────────────────────────────────
    "SBS-AHU-107": {
        "name": "CHW / HW / VFD / Econ-DB — Basic CHW-HW",
        "description": "Standard CHW/HW AHU: dry bulb economizer, fixed ventilation",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-chw", "htg-hw", "econ-db",
            "vent-fix", "opt-start",
        ] + _SAFETY_BASE,
    },
    "SBS-AHU-108": {
        "name": "CHW / HW / VFD / Econ-Enth — Standard Enthalpy",
        "description": "Standard CHW/HW AHU: enthalpy economizer, fixed ventilation",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-chw", "htg-hw", "econ-enth",
            "vent-fix", "opt-start",
        ] + _SAFETY_BASE,
    },
    "SBS-AHU-109": {
        "name": "CHW / HW / VFD / Econ-Enth / RF-VFD — With Return Fan",
        "description": "CHW/HW AHU with return fan VFD for building pressure control",
        "modules": [
            "core", "fan-sf-vfd", "fan-rf-vfd",
            "clg-chw", "htg-hw", "econ-enth",
            "vent-fix", "opt-start",
        ] + _SAFETY_FULL,
    },
    "SBS-AHU-110": {
        "name": "CHW / HW / VFD / Econ-Enth / EF-VFD — With Exhaust Fan",
        "description": "CHW/HW AHU with exhaust fan VFD tracking OA airflow",
        "modules": [
            "core", "fan-sf-vfd", "fan-ef-vfd",
            "clg-chw", "htg-hw", "econ-enth",
            "vent-ams", "opt-start",
        ] + _SAFETY_FULL_EA,
    },

    # ── CHW / HW WITH ERW (111-113) ─────────────────────────────────────
    "SBS-AHU-111": {
        "name": "CHW / HW / VFD / Econ-Enth / ERW — Standard ERW",
        "description": "CHW/HW AHU with energy recovery wheel, no exhaust fan",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-chw", "htg-hw", "econ-enth", "erw",
            "vent-fix", "opt-start",
        ] + _SAFETY_FULL,
    },
    "SBS-AHU-112": {
        "name": "CHW / HW / VFD / EF-VFD / Econ-Enth / ERW — Full ERW",
        "description": "CHW/HW AHU with ERW + exhaust fan VFD + OA airflow",
        "modules": [
            "core", "fan-sf-vfd", "fan-ef-vfd",
            "clg-chw", "htg-hw", "econ-enth", "erw",
            "vent-ams", "opt-start",
        ] + _SAFETY_FULL_EA,
    },
    "SBS-AHU-113": {
        "name": "CHW / HW / VFD / EF-VFD / Econ-Enth / ERW / DCV-CO2 — ERW + DCV",
        "description": "Full-featured: CHW/HW, ERW, exhaust fan, DCV-CO2 ventilation — the A201",
        "modules": [
            "core", "fan-sf-vfd", "fan-ef-vfd",
            "clg-chw", "htg-hw", "econ-enth", "erw",
            "dcv-co2", "opt-start",
        ] + _SAFETY_FULL_EA,
    },

    # ── WITH PREHEAT (114-115) ──────────────────────────────────────────
    "SBS-AHU-114": {
        "name": "CHW / HW / PH-HW / VFD / Econ-Enth — With Preheat",
        "description": "CHW/HW AHU with hot water preheat coil + pump",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-chw", "htg-hw", "ph-hw", "econ-enth",
            "vent-fix", "opt-start",
        ] + _SAFETY_FULL,
    },
    "SBS-AHU-115": {
        "name": "CHW / HW / PH-HW / VFD / EF-VFD / Econ-Enth / ERW — Preheat + ERW",
        "description": "Full preheat config: CHW/HW, preheat, ERW, exhaust fan",
        "modules": [
            "core", "fan-sf-vfd", "fan-ef-vfd",
            "clg-chw", "htg-hw", "ph-hw", "econ-enth", "erw",
            "vent-ams", "opt-start",
        ] + _SAFETY_FULL_EA,
    },

    # ── WITH HUMIDITY (116-117) ─────────────────────────────────────────
    "SBS-AHU-116": {
        "name": "CHW / HW / VFD / Econ-Enth / HUM-STM — With Humidifier",
        "description": "CHW/HW AHU with steam humidifier",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-chw", "htg-hw", "econ-enth", "hum-stm",
            "vent-fix", "opt-start",
        ] + _SAFETY_FULL,
    },
    "SBS-AHU-117": {
        "name": "CHW / HW / VFD / Econ-Enth / DEHUM-SC — With Dehumidification",
        "description": "CHW/HW AHU with subcooling dehumidification",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-chw", "htg-hw", "econ-enth", "dehum-sc",
            "vent-fix", "opt-start",
        ] + _SAFETY_FULL,
    },

    # ── DOAS / 100% OA (118-119) ────────────────────────────────────────
    "SBS-AHU-118": {
        "name": "DOAS — CHW / PH-HW / ERW / 100% OA",
        "description": "Dedicated outdoor air system: 100% OA, CHW, HW preheat, ERW",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-chw", "ph-hw", "erw",
            "vent-100",
        ] + _SAFETY_FULL,
    },
    "SBS-AHU-119": {
        "name": "DOAS — DX-2 / PH-HW / ERW / 100% OA",
        "description": "Dedicated outdoor air system: 100% OA, DX cooling, HW preheat, ERW",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-dx-2", "ph-hw", "erw",
            "vent-100",
        ] + _SAFETY_FULL,
    },

    # ── MAXIMUM COMPLEXITY (120) ────────────────────────────────────────
    "SBS-AHU-120": {
        "name": "FULL — CHW / HW / PH-HW / VFD / EF-VFD / Econ-Enth / ERW / DCV-CO2 / HUM / DEHUM",
        "description": "Maximum complexity: every feature enabled — CHW, HW, preheat, ERW, exhaust, DCV, humidifier, dehumid",
        "modules": [
            "core", "fan-sf-vfd", "fan-ef-vfd",
            "clg-chw", "htg-hw", "ph-hw",
            "econ-enth", "erw",
            "dcv-co2", "hum-stm", "dehum-sc",
            "opt-start",
        ] + _SAFETY_FULL_EA + ["safe-cond-ovf"],
    },
}
