"""
SBS Controls Modular Composition Engine for Reliable Controls

Takes equipment type + feature selections and generates a complete controller
configuration including BACnet objects, I/O mapping, and Control-BASIC code.

Architecture:
    - Each module is a self-contained dict defining objects, I/O, and code
    - The assembler merges modules, resolves dependencies, and deduplicates
    - The controller selector picks the right hardware for the I/O count
    - Output feeds into the existing generator/pan_binary pipeline

Module Categories (exec_order ranges):
    10 = Modes / Configuration
    20 = Occupancy / Scheduling
    30 = Fan Control
    40 = Economizer / Dampers
    50 = Cooling
    60 = Heating
    70 = Pressure Control
    80 = Safety / Protection
    90 = Alarms / Monitoring
"""

from typing import Dict, List, Optional

# ── Module Registry ──────────────────────────────────────────────────────────
# All registered modules keyed by module ID
_MODULE_REGISTRY: Dict[str, dict] = {}

# Base equipment modules keyed by equipment type code
_BASE_REGISTRY: Dict[str, dict] = {}


def register_module(module: dict) -> None:
    """Register a feature module in the global registry."""
    mid = module["id"]
    if mid in _MODULE_REGISTRY:
        raise ValueError(f"Duplicate module ID: {mid}")
    _validate_module(module)
    _MODULE_REGISTRY[mid] = module


def register_base(equipment_type: str, module: dict) -> None:
    """Register a base equipment module."""
    if equipment_type in _BASE_REGISTRY:
        raise ValueError(f"Duplicate base equipment type: {equipment_type}")
    _validate_module(module)
    _BASE_REGISTRY[equipment_type] = module


def get_module(module_id: str) -> Optional[dict]:
    """Retrieve a registered feature module by ID."""
    return _MODULE_REGISTRY.get(module_id)


def get_base(equipment_type: str) -> Optional[dict]:
    """Retrieve a registered base equipment module by type code."""
    return _BASE_REGISTRY.get(equipment_type)


def list_modules() -> List[dict]:
    """Return all registered feature modules."""
    return list(_MODULE_REGISTRY.values())


def list_bases() -> List[str]:
    """Return all registered base equipment type codes."""
    return list(_BASE_REGISTRY.keys())


def get_modules_for_feature(feature_code: str) -> List[dict]:
    """Find all modules matching a feature code."""
    return [m for m in _MODULE_REGISTRY.values() if m.get("feature") == feature_code]


# ── Validation ───────────────────────────────────────────────────────────────

REQUIRED_KEYS = {"id", "name", "category", "exec_order", "objects", "code"}
VALID_OBJECT_TYPES = {"AI", "AO", "AV", "BI", "BO", "BV", "MO", "MV", "LOOP", "SCHEDULE"}
VALID_CATEGORIES = {
    "core", "mode", "occupancy", "fan", "damper", "economizer",
    "cooling", "heating", "pressure", "safety", "alarm", "monitoring",
    "plant", "pump", "valve", "generic",
}


def _validate_module(module: dict) -> None:
    """Validate module structure. Raises ValueError on problems."""
    missing = REQUIRED_KEYS - set(module.keys())
    if missing:
        raise ValueError(f"Module '{module.get('id', '??')}' missing keys: {missing}")

    # Validate objects dict
    objects = module["objects"]
    if not isinstance(objects, dict):
        raise ValueError(f"Module '{module['id']}': objects must be a dict")

    for obj_type, obj_list in objects.items():
        if obj_type not in VALID_OBJECT_TYPES:
            raise ValueError(
                f"Module '{module['id']}': invalid object type '{obj_type}'. "
                f"Valid: {VALID_OBJECT_TYPES}"
            )
        if not isinstance(obj_list, list):
            raise ValueError(
                f"Module '{module['id']}': objects['{obj_type}'] must be a list"
            )
        for obj in obj_list:
            if "name" not in obj:
                raise ValueError(
                    f"Module '{module['id']}': object in '{obj_type}' missing 'name'"
                )

    # Validate exec_order
    if not isinstance(module["exec_order"], int) or not (0 <= module["exec_order"] <= 100):
        raise ValueError(
            f"Module '{module['id']}': exec_order must be int 0-100"
        )


# ── Auto-import all module files ─────────────────────────────────────────────
# Import base equipment modules and feature modules so they self-register

def _auto_import():
    """Import all module files in this package to trigger registration."""
    import importlib
    import pkgutil
    import os

    pkg_dir = os.path.dirname(__file__)
    for _importer, modname, _ispkg in pkgutil.iter_modules([pkg_dir]):
        if modname.startswith("mod_") or modname.startswith("base_"):
            importlib.import_module(f".{modname}", package=__name__)


_auto_import()
