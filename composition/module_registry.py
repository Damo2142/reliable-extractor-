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


# Standard AHU-VAV configurations
STANDARD_CONFIGS = {
    "AHU-VAV-CHW-HW-ECON-ERW": {
        "name": "Standard CHW/HW AHU with Economizer and ERW",
        "description": "Full-featured AHU: CHW cooling, HW heating, enthalpy economizer, ERW, exhaust fan VFD, DCV-CO2",
        "modules": [
            "core", "fan-sf-vfd", "fan-ef-vfd",
            "htg-hw", "clg-chw", "econ-enth", "erw",
            "dcv-co2", "opt-start",
            "safe-freeze", "safe-smoke", "safe-hi-static", "safe-filter",
            "safe-filter-oa", "safe-filter-final", "safe-filter-ea",
        ],
    },
    "AHU-VAV-CHW-HW-ECON": {
        "name": "CHW/HW AHU with Economizer (no ERW)",
        "description": "Standard AHU: CHW cooling, HW heating, enthalpy economizer, return fan VFD",
        "modules": [
            "core", "fan-sf-vfd", "fan-rf-vfd",
            "htg-hw", "clg-chw", "econ-enth",
            "vent-fix", "opt-start",
            "safe-freeze", "safe-smoke", "safe-filter",
        ],
    },
    "AHU-VAV-DX-ELEC-ECON": {
        "name": "DX/Electric AHU with Economizer",
        "description": "Packaged RTU: DX cooling, electric heat, dry bulb economizer",
        "modules": [
            "core", "fan-sf-vfd",
            "htg-elec-2", "clg-dx-2", "econ-db",
            "vent-fix", "opt-start",
            "safe-freeze", "safe-smoke", "safe-filter",
        ],
    },
    "AHU-VAV-CHW-ONLY": {
        "name": "CHW-Only AHU (no heating)",
        "description": "Cooling-only AHU with CHW coil",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-chw", "econ-db",
            "vent-fix", "opt-start",
            "safe-smoke", "safe-filter",
        ],
    },
    "DOAS-CHW-HW-ERW": {
        "name": "DOAS with CHW/HW and ERW",
        "description": "Dedicated outdoor air system — 100% OA, CHW, HW preheat, ERW",
        "modules": [
            "core", "fan-sf-vfd",
            "ph-hw", "clg-chw", "erw",
            "vent-100",
            "safe-freeze", "safe-smoke", "safe-filter",
        ],
    },
}
