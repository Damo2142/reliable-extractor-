"""
SBS Controls -- Module Assembler to .pan Binary Bridge

Converts the output from assembler.assemble() into Reliable Controls .pan
binary format using pan_binary.py's PanWriter (template-based) or outputs
a .pan.json intermediate file for later binary conversion.

Two modes of operation:

1. **Template mode** (preferred): Takes a blank .panx template for the
   selected controller model, populates it with assembled objects using
   PanWriter's in-place editing. Produces a real .pan/.panx file.

2. **JSON mode** (fallback): Generates a complete .pan-ready data structure
   as JSON. This intermediate format captures everything needed to build the
   binary later, and serves as a human-readable audit trail.

Usage:
    from app.modules.pan_generator import generate_pan, compose_and_generate

    # From assembler output:
    result = assemble("AHU-VAV", ["CHW", "HW"], "AHU-01")
    pan_path = generate_pan(result, "AHU-01", device_id=1)

    # One-shot convenience:
    pan_path = compose_and_generate("AHU-VAV", ["CHW","HW"], "AHU-01")
"""

import json
import struct
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# BACnet constants (mirrored from pan_binary.py for independence)
# ---------------------------------------------------------------------------

TYPE_IDS = {
    'AI': 0, 'AO': 1, 'AV': 2, 'BI': 3, 'BO': 4, 'BV': 5,
    'CALENDAR': 6, 'COMMAND': 7, 'DEVICE': 8,
    'LOOP': 12, 'MI': 13, 'MO': 14, 'PROGRAM': 16,
    'SCHEDULE': 17, 'MV': 19, 'TREND': 20,
}

BACNET_TYPES = {v: k for k, v in TYPE_IDS.items()}

# BACnet engineering units: name -> enum value
# Reverse of the table in pan_binary.py PanBinary.get_point_details()
UNIT_ENUMS = {
    'no-units': 95,
    'deg-f': 64,
    'deg-c': 62,
    'percent': 59,
    'percent-rh': 34,
    'percent-open': 91,
    'psi': 69,
    'inches-of-water': 71,
    'cubic-feet-per-minute': 45,
    'cfm': 45,
    'minutes': 80,
    'seconds': 81,
    'hours': 82,
    'hertz': 31,
    'revolutions-per-minute': 85,
    'rpm': 85,
    'watts': 17,
    'kilowatts': 18,
    'amperes': 4,
    'volts': 6,
    'ppm': 57,
    'parts-per-million': 57,
    'feet': 38,
    'inches': 37,
    'meters': 36,
    'liters-per-second': 48,
    'us-gallons-per-minute': 50,
    'btus-per-hour': 21,
    'sq-feet': 2,
}

# Property IDs used in .pan binary
PROP_PRESENT_VALUE = 0x55
PROP_UNITS = 0x75
PROP_OUT_OF_SERVICE = 0x51
PROP_RELINQUISH_DEFAULT = 0x68
PROP_STATUS_FLAGS = 0x71
PROP_PROGRAM_ENABLED = 0x0A
PROP_RANGE = 0x1D
PROP_MIN_VALUE = 0x3B
PROP_MAX_VALUE = 0x2D
PROP_WEEKLY_SCHEDULE = 0x7B
PROP_SCHEDULE_DEFAULT = 0xAE

# Default blanks directory
BLANKS_DIR = Path("/srv/dfa/shared/files/vendors/reliable/blanks")


# ---------------------------------------------------------------------------
# Instance number assignment
# ---------------------------------------------------------------------------

def assign_instances(objects: Dict[str, list]) -> Dict[str, list]:
    """Assign BACnet instance numbers to assembled objects.

    Each object type gets its own instance counter starting at 1.
    Objects are processed in the order they appear (which is exec_order
    from the assembler).

    Returns a new dict with 'instance' added to each object.
    """
    result = {}
    for obj_type, obj_list in objects.items():
        counter = 1
        result[obj_type] = []
        for obj in obj_list:
            enriched = dict(obj)
            enriched['instance'] = counter
            enriched['bacnet_type_id'] = TYPE_IDS.get(obj_type, 0)
            enriched['bacnet_objid'] = encode_objid_int(obj_type, counter)
            counter += 1
            result[obj_type].append(enriched)
    return result


def encode_objid_int(type_name: str, instance: int) -> int:
    """Encode BACnet Object Identifier as a 32-bit integer."""
    type_id = TYPE_IDS.get(type_name, 0)
    return (type_id << 22) | (instance & 0x3FFFFF)


def encode_objid_bytes(type_name: str, instance: int) -> bytes:
    """Encode BACnet Object Identifier as 4-byte big-endian bytes."""
    return struct.pack('>I', encode_objid_int(type_name, instance))


def resolve_unit_enum(unit_str: str) -> int:
    """Convert a unit name string to BACnet engineering units enum value."""
    if unit_str is None:
        return 95  # no-units
    return UNIT_ENUMS.get(unit_str.lower().strip(), 95)


# ---------------------------------------------------------------------------
# Pan-ready data structure builder
# ---------------------------------------------------------------------------

def build_pan_structure(
    assembly_result: dict,
    device_name: str,
    device_id: int = 1,
) -> dict:
    """Convert assembler output into a .pan-ready data structure.

    This is the canonical intermediate format that captures everything
    needed for binary .pan generation:
      - All BACnet objects with instance numbers and encoded ObjIDs
      - Properties formatted as binary property entries
      - Program object with assembled Control-BASIC code
      - Loop objects with PID bindings (from assembler loop config)
      - Schedule objects with weekly schedule data

    Args:
        assembly_result: Output from assembler.assemble()
        device_name: Final device name (e.g., "AHU-01")
        device_id: BACnet device instance (e.g., 1)

    Returns:
        dict with complete .pan-ready structure
    """
    objects = assembly_result.get('objects', {})
    code = assembly_result.get('code', '')
    io_map = assembly_result.get('io_map', {})
    controller = assembly_result.get('controller', None)
    point_list = assembly_result.get('point_list', [])

    # Apply device name substitution if not already done
    substituted_objects = {}
    for obj_type, obj_list in objects.items():
        substituted_objects[obj_type] = []
        for obj in obj_list:
            new_obj = dict(obj)
            new_obj['name'] = new_obj['name'].replace('{device-name}', device_name)
            if 'desc' in new_obj:
                new_obj['desc'] = new_obj.get('desc', '').replace('{device-name}', device_name)
            substituted_objects[obj_type].append(new_obj)

    if '{device-name}' in code:
        code = code.replace('{device-name}', device_name)

    # Assign instance numbers
    instanced_objects = assign_instances(substituted_objects)

    # Build name-to-objid lookup for loop/schedule cross-references
    name_to_objid = {}
    for obj_type, obj_list in instanced_objects.items():
        for obj in obj_list:
            name_to_objid[obj['name']] = {
                'type': obj_type,
                'instance': obj['instance'],
                'objid': obj['bacnet_objid'],
            }

    # Build binary-ready object entries
    pan_objects = []

    # Standard BACnet point objects (AI, AO, AV, BI, BO, BV, MO, MV)
    for obj_type in ['AI', 'AO', 'AV', 'BI', 'BO', 'BV', 'MO', 'MV']:
        for obj in instanced_objects.get(obj_type, []):
            pan_obj = _build_point_object(obj, obj_type)
            pan_objects.append(pan_obj)

    # Loop objects
    for obj in instanced_objects.get('LOOP', []):
        pan_obj = _build_loop_object(obj, name_to_objid)
        pan_objects.append(pan_obj)

    # Schedule objects
    for obj in instanced_objects.get('SCHEDULE', []):
        pan_obj = _build_schedule_object(obj)
        pan_objects.append(pan_obj)

    # Program object for the assembled code
    if code.strip():
        program_obj = _build_program_object(device_name, code)
        pan_objects.append(program_obj)

    # Controller model info
    ctrl_info = {}
    if controller:
        if hasattr(controller, 'model'):
            ctrl_info = {
                'model': controller.model,
                'family': getattr(controller, 'family', ''),
                'description': getattr(controller, 'description', ''),
            }
        elif isinstance(controller, dict):
            ctrl_info = controller
        else:
            ctrl_info = {'summary': str(controller)}

    # Build the complete structure
    pan_structure = {
        '_format': 'pan-ready-v1',
        '_generated': datetime.now().isoformat(),
        '_generator': 'SBS Controls Module Assembler -> Pan Generator',
        'device': {
            'name': device_name,
            'device_id': device_id,
            'bacnet_objid': encode_objid_int('DEVICE', device_id),
        },
        'controller': ctrl_info,
        'equipment_type': assembly_result.get('equipment_type', ''),
        'modules_loaded': assembly_result.get('modules', []),
        'io_map': {k: v.replace('{device-name}', device_name) for k, v in io_map.items()},
        'io_counts': assembly_result.get('io_counts', {}),
        'objects': pan_objects,
        'object_summary': {
            obj_type: len(obj_list)
            for obj_type, obj_list in instanced_objects.items()
            if obj_list
        },
        'total_objects': len(pan_objects),
        'code': code,
        'code_lines': len(code.strip().splitlines()) if code.strip() else 0,
        'warnings': assembly_result.get('warnings', []),
    }

    return pan_structure


def _build_point_object(obj: dict, obj_type: str) -> dict:
    """Build a pan-ready entry for a standard BACnet point object."""
    unit_enum = resolve_unit_enum(obj.get('units'))
    default_val = obj.get('default')
    present_value = default_val if default_val is not None else 0.0

    # For binary points, present value is 0 or 1
    if obj_type in ('BI', 'BO', 'BV'):
        if isinstance(present_value, bool):
            present_value = 1.0 if present_value else 0.0
        elif isinstance(present_value, (int, float)):
            present_value = float(present_value)
        else:
            present_value = 0.0

    properties = {
        'present_value': {
            'prop_id': PROP_PRESENT_VALUE,
            'tag': 'float' if obj_type not in ('BI', 'BO', 'BV') else 'bool',
            'value': present_value,
        },
        'units': {
            'prop_id': PROP_UNITS,
            'tag': 'uint8',
            'value': unit_enum,
        },
        'out_of_service': {
            'prop_id': PROP_OUT_OF_SERVICE,
            'tag': 'bool',
            'value': False,
        },
    }

    # Relinquish default for output types
    if obj_type in ('AO', 'BO', 'BV', 'AV', 'MO', 'MV'):
        rel_default = default_val if default_val is not None else 0.0
        properties['relinquish_default'] = {
            'prop_id': PROP_RELINQUISH_DEFAULT,
            'tag': 'float',
            'value': float(rel_default),
        }

    # Min/max for analog types
    if obj_type in ('AI', 'AO', 'AV') and obj.get('min') is not None:
        properties['min_value'] = {
            'prop_id': PROP_MIN_VALUE,
            'tag': 'float',
            'value': float(obj['min']),
        }
    if obj_type in ('AI', 'AO', 'AV') and obj.get('max') is not None:
        properties['max_value'] = {
            'prop_id': PROP_MAX_VALUE,
            'tag': 'float',
            'value': float(obj['max']),
        }

    # Binary states
    states = obj.get('states')

    return {
        'name': obj['name'],
        'type': obj_type,
        'type_id': TYPE_IDS.get(obj_type, 0),
        'instance': obj['instance'],
        'objid': obj['bacnet_objid'],
        'description': obj.get('desc', ''),
        'properties': properties,
        'states': states,
    }


def _build_loop_object(obj: dict, name_to_objid: dict) -> dict:
    """Build a pan-ready entry for a LOOP object.

    Loop objects contain PID control bindings:
      - input_ref: controlled variable (e.g., supply air temp sensor)
      - setpoint_ref: setpoint source (e.g., SAT setpoint AV)
      - output_ref: manipulated variable (e.g., valve command AO)
    """
    properties = {}

    # PID parameters from module definition
    if obj.get('proportional') is not None:
        properties['proportional'] = {
            'prop_id': 0x5D,
            'tag': 'float',
            'value': float(obj['proportional']),
        }
    if obj.get('integral') is not None:
        properties['integral'] = {
            'prop_id': 0x6C,
            'tag': 'float',
            'value': float(obj['integral']),
        }
    if obj.get('derivative') is not None:
        properties['derivative'] = {
            'prop_id': 0x0E,
            'tag': 'float',
            'value': float(obj.get('derivative', 0.0)),
        }

    # Action (direct/reverse)
    action = obj.get('action', 'direct')
    properties['action'] = {
        'prop_id': 0x1C,
        'tag': 'enum',
        'value': 1 if action == 'reverse' else 0,
    }

    # Cross-references to input/setpoint/output objects
    refs = {}
    for ref_key in ('input_ref', 'setpoint_ref', 'output_ref'):
        ref_name = obj.get(ref_key)
        if ref_name:
            # Resolve the reference name to an ObjID
            ref_info = name_to_objid.get(ref_name)
            if ref_info:
                refs[ref_key] = {
                    'name': ref_name,
                    'type': ref_info['type'],
                    'instance': ref_info['instance'],
                    'objid': ref_info['objid'],
                }
            else:
                refs[ref_key] = {
                    'name': ref_name,
                    'type': 'UNRESOLVED',
                    'instance': 0,
                    'objid': 0,
                }

    return {
        'name': obj['name'],
        'type': 'LOOP',
        'type_id': TYPE_IDS['LOOP'],
        'instance': obj['instance'],
        'objid': obj['bacnet_objid'],
        'description': obj.get('desc', ''),
        'properties': properties,
        'refs': refs,
    }


def _build_schedule_object(obj: dict) -> dict:
    """Build a pan-ready entry for a SCHEDULE object."""
    properties = {}

    # Schedule default value
    default_val = obj.get('default', 0.0)
    properties['schedule_default'] = {
        'prop_id': PROP_SCHEDULE_DEFAULT,
        'tag': 'float',
        'value': float(default_val) if default_val is not None else 0.0,
    }

    # Weekly schedule: default to Mon-Fri occupied, Sat-Sun unoccupied
    weekly = obj.get('weekly_schedule')
    if weekly is None:
        # Default: weekdays on (1), weekends off (0)
        weekly = {
            'Mon': 1, 'Tue': 1, 'Wed': 1, 'Thu': 1, 'Fri': 1,
            'Sat': 0, 'Sun': 0,
        }
    properties['weekly_schedule'] = {
        'prop_id': PROP_WEEKLY_SCHEDULE,
        'tag': 'schedule',
        'value': weekly,
    }

    return {
        'name': obj['name'],
        'type': 'SCHEDULE',
        'type_id': TYPE_IDS['SCHEDULE'],
        'instance': obj['instance'],
        'objid': obj['bacnet_objid'],
        'description': obj.get('desc', ''),
        'properties': properties,
    }


def _build_program_object(device_name: str, code: str) -> dict:
    """Build a pan-ready entry for the PROGRAM object containing Control-BASIC."""
    return {
        'name': f"{device_name}-PRG",
        'type': 'PROGRAM',
        'type_id': TYPE_IDS['PROGRAM'],
        'instance': 1,
        'objid': encode_objid_int('PROGRAM', 1),
        'description': f"Control program for {device_name}",
        'properties': {
            'program_enabled': {
                'prop_id': PROP_PROGRAM_ENABLED,
                'tag': 'uint8',
                'value': 1,
            },
        },
        'code': code,
        'code_lines': len(code.strip().splitlines()),
    }


# ---------------------------------------------------------------------------
# Template-based .pan generation (using PanWriter on a blank)
# ---------------------------------------------------------------------------

def _find_blank_template(controller_model: str) -> Optional[Path]:
    """Find a blank .panx template for the given controller model.

    Looks in the blanks directory for a matching controller family.
    """
    if not BLANKS_DIR.exists():
        return None

    # Map controller model names to blank folder names
    model_map = {
        'MPA-33': 'MACH-ProAir-08',
        'MPA-34': 'MACH-ProAir-08',
        'MPA-35': 'MACH-ProAir-18',
        'MPA-36': 'MACH-ProAir-18',
        'MPZ-44': 'MACH-ProZone-44',
        'MPZ-88': 'MACH-ProWebSys-88',
        'MPWS': 'MACH-ProWebSys-88',
        'MPC': 'MACH-ProWebSys-88',
        'MP2': 'MACH-Pro2-C8',
    }

    blank_name = model_map.get(controller_model)
    if blank_name:
        panx = BLANKS_DIR / blank_name / f"{blank_name}.panx"
        if panx.exists():
            return panx

    # Fallback: search for any matching pattern
    for d in BLANKS_DIR.iterdir():
        if d.is_dir():
            for panx in d.glob("*.panx"):
                if controller_model.lower().replace('-', '') in d.name.lower().replace('-', ''):
                    return panx

    return None


def _apply_to_template(
    pan_structure: dict,
    template_path: Path,
    output_path: Path,
) -> bool:
    """Apply the pan-ready structure to a template .panx using PanWriter.

    This modifies the template binary in-place:
    1. Sets the device ID
    2. Renames the device (if template has a default name)
    3. Sets present values for all matching objects
    4. Sets loop bindings

    Returns True if successful, False if the template could not be used.
    """
    try:
        from app.pan_binary import PanWriter, PanBinary
    except ImportError:
        logger.warning("pan_binary module not available for template mode")
        return False

    try:
        writer = PanWriter.from_panx(template_path)
    except Exception as e:
        logger.warning(f"Failed to load template {template_path}: {e}")
        return False

    # Set device ID
    device_id = pan_structure['device']['device_id']
    writer.set_device_id(device_id)

    # Parse the template to find existing object names
    reader = PanBinary(bytes(writer.data))
    template_objects = {obj['name'] for obj in reader.objects}

    device_name = pan_structure['device']['name']
    applied_count = 0

    # Try to set present values for objects that exist in the template
    for pan_obj in pan_structure['objects']:
        obj_name = pan_obj['name']
        props = pan_obj.get('properties', {})

        pv_prop = props.get('present_value', {})
        if pv_prop and isinstance(pv_prop.get('value'), (int, float)):
            if writer.set_present_value(obj_name, float(pv_prop['value'])):
                applied_count += 1

    # Set loop bindings
    for pan_obj in pan_structure['objects']:
        if pan_obj['type'] != 'LOOP':
            continue
        refs = pan_obj.get('refs', {})
        input_ref = refs.get('input_ref', {})
        setpoint_ref = refs.get('setpoint_ref', {})

        if input_ref.get('type') != 'UNRESOLVED' or setpoint_ref.get('type') != 'UNRESOLVED':
            writer.set_loop_binding(
                pan_obj['name'],
                input_type=input_ref.get('type') if input_ref.get('type') != 'UNRESOLVED' else None,
                input_instance=input_ref.get('instance'),
                setpoint_type=setpoint_ref.get('type') if setpoint_ref.get('type') != 'UNRESOLVED' else None,
                setpoint_instance=setpoint_ref.get('instance'),
            )

    # Save as .panx
    if str(output_path).endswith('.panx'):
        meta = {
            "Device": device_id,
            "Database": f"{device_id}.pan",
            "Model": pan_structure.get('controller', {}).get('model', ''),
        }
        writer.save_panx(output_path, meta=meta)
    else:
        writer.save(output_path)

    logger.info(
        f"Template-based generation: applied {applied_count} present values "
        f"to {output_path}"
    )
    return True


# ---------------------------------------------------------------------------
# Main generation functions
# ---------------------------------------------------------------------------

def generate_pan(
    assembly_result: dict,
    device_name: str,
    device_id: int = 1,
    output_path: Optional[str] = None,
    output_dir: str = "/tmp",
    use_template: bool = True,
) -> str:
    """Generate a .pan file from assembler output.

    Attempts template-based generation first (real .panx binary). Falls back
    to JSON intermediate format if no suitable template is found.

    Args:
        assembly_result: Output dict from assembler.assemble()
        device_name: Equipment tag (e.g., "AHU-01")
        device_id: BACnet device instance number
        output_path: Explicit output file path (overrides output_dir)
        output_dir: Directory for output files (default: /tmp)
        use_template: Whether to attempt template-based binary generation

    Returns:
        Path to the generated file (.panx if template worked, .pan.json otherwise)
    """
    # Build the canonical pan-ready structure
    pan_structure = build_pan_structure(assembly_result, device_name, device_id)

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Attempt template-based binary generation
    if use_template:
        ctrl = assembly_result.get('controller')
        model = None
        if ctrl:
            if hasattr(ctrl, 'model'):
                model = ctrl.model
            elif isinstance(ctrl, dict):
                model = ctrl.get('model')

        if model:
            template_path = _find_blank_template(model)
            if template_path:
                if output_path:
                    panx_path = Path(output_path)
                else:
                    panx_path = out_dir / f"{device_name}.panx"

                if _apply_to_template(pan_structure, template_path, panx_path):
                    # Also save the JSON alongside for reference
                    json_path = panx_path.with_suffix('.pan.json')
                    _save_json(pan_structure, json_path)
                    logger.info(f"Generated .panx: {panx_path}")
                    print(f"  [BINARY] {panx_path}")
                    print(f"  [JSON]   {json_path}")
                    return str(panx_path)

    # Fallback: save as JSON intermediate format
    if output_path:
        json_path = Path(output_path)
        if not json_path.suffix:
            json_path = json_path.with_suffix('.pan.json')
    else:
        json_path = out_dir / f"{device_name}.pan.json"

    _save_json(pan_structure, json_path)
    logger.info(f"Generated .pan.json: {json_path}")
    return str(json_path)


def _save_json(pan_structure: dict, path: Path):
    """Save pan structure as formatted JSON."""
    path.write_text(json.dumps(pan_structure, indent=2, default=str))


def compose_and_generate(
    equipment_type: str,
    features: List[str],
    device_name: str,
    device_id: int = 1,
    output_dir: str = "/tmp",
) -> str:
    """One-shot: run assembler then generate .pan file.

    Args:
        equipment_type: Base equipment type (e.g., "AHU-VAV")
        features: List of feature codes (e.g., ["CHW", "HW", "ECON-DB"])
        device_name: Equipment tag (e.g., "AHU-01")
        device_id: BACnet device instance number
        output_dir: Directory for output files

    Returns:
        Path to the generated file
    """
    from app.modules.assembler import assemble

    assembly_result = assemble(
        equipment_type=equipment_type,
        features=features,
        device_name=device_name,
    )

    return generate_pan(
        assembly_result=assembly_result,
        device_name=device_name,
        device_id=device_id,
        output_dir=output_dir,
    )


# ---------------------------------------------------------------------------
# Template Library Mode — keeps {device-name} placeholders
# ---------------------------------------------------------------------------

def assemble_as_library_json(
    equipment_type: str,
    features: List[str],
    output_path: Optional[str] = None,
    output_dir: str = "/tmp",
) -> str:
    """Assemble a composition and output as a library-format JSON.

    This is TEMPLATE MODE — point names keep {device-name} placeholders.
    The output JSON matches the format expected by generator.py (the existing
    XML generator that feeds PFG).

    This is how we build the template library:
      1. assemble_as_library_json() → library JSON with {device-name}
      2. generator.py generates XML from library JSON
      3. PFG merges XML + blank .pan → output .pan template

    Args:
        equipment_type: Base type code (e.g., "AHU-VAV")
        features: List of feature codes
        output_path: Explicit output path (optional)
        output_dir: Directory for output (default: /tmp)

    Returns:
        Path to the generated library JSON file
    """
    from app.modules.assembler import assemble

    # Assemble with {device-name} as the device name — keeps templates
    assembly_result = assemble(
        equipment_type=equipment_type,
        features=features,
        device_name="{device-name}",
    )

    # Convert to library JSON format (compatible with generator.py)
    library_json = _to_library_format(assembly_result, equipment_type, features)

    # Save
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if output_path:
        json_path = Path(output_path)
    else:
        # Build filename from type + features
        feat_str = "_".join(sorted(features))[:60]
        json_path = out_dir / f"{equipment_type}_{feat_str}.json"

    json_path.write_text(json.dumps(library_json, indent=2, default=str))
    logger.info(f"Generated library JSON (template mode): {json_path}")
    return str(json_path)


def generate_pan_via_pfg(
    equipment_type: str,
    features: List[str],
    device_name: str = "{device-name}",
    device_id: str = "900",
    blank_model: str = None,
    output_dir: str = "/tmp",
) -> str:
    """Full pipeline: Assemble → Library JSON → XML → PFG → .pan

    This uses the existing composer pipeline (generator.py + PFG under wine)
    to produce a real .pan binary file.

    Args:
        equipment_type: Base type code
        features: Feature codes
        device_name: Device name ({device-name} for templates, or actual name)
        device_id: BACnet device instance
        blank_model: Controller blank folder name (auto-detected if None)
        output_dir: Output directory

    Returns:
        Path to generated .pan file
    """
    import sys
    import shutil
    import time

    from app.modules.assembler import assemble

    # Step 1: Assemble
    assembly_result = assemble(
        equipment_type=equipment_type,
        features=features,
        device_name=device_name,
    )

    # Step 2: Convert to library format
    library_json = _to_library_format(assembly_result, equipment_type, features)

    # Step 3: Generate XML via generator.py
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from generator import generate_xml

    xml_content = generate_xml(
        library_json,
        device_id=device_id,
        device_name=device_name,
        pfg_safe=True,
    )

    # Step 4: Find blank template
    ctrl = assembly_result.get('controller')
    if not blank_model and ctrl:
        model = ctrl.model if hasattr(ctrl, 'model') else ctrl.get('model', '')
        template_path = _find_blank_template(model)
        if template_path:
            blank_model = template_path.parent.name

    if not blank_model:
        logger.warning("No blank controller template found — saving XML only")
        xml_path = Path(output_dir) / f"{equipment_type}_changes.xml"
        xml_path.write_text(xml_content)
        return str(xml_path)

    # Step 5: Run PFG pipeline
    work_dir = Path(f"/tmp/sbs_compose_{int(time.time())}")
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Write changes XML
        changes_xml = work_dir / "changes.xml"
        changes_xml.write_text(xml_content)

        # Extract blank .pan from .panx
        blank_panx = BLANKS_DIR / blank_model
        panx_files = list(blank_panx.glob("*.panx"))
        if not panx_files:
            raise ValueError(f"No .panx in blanks/{blank_model}")

        # Extract .pan from .panx (it's a zip)
        import zipfile
        tmp_zip = work_dir / "blank.zip"
        shutil.copy2(panx_files[0], tmp_zip)
        extract_dir = work_dir / "blank_contents"
        with zipfile.ZipFile(tmp_zip, 'r') as zf:
            zf.extractall(extract_dir)
        pan_files = list(extract_dir.rglob("*.pan"))
        if not pan_files:
            raise ValueError(f"No .pan inside {panx_files[0].name}")
        input_pan = pan_files[0]

        # Run PFG
        output_pan = work_dir / f"{equipment_type}.pan"
        pfg_path = Path("/srv/reliable-generator-dev/pfg/pfg")
        if not pfg_path.exists():
            pfg_path = Path("/srv/reliable-generator-dev/pfg/PanelFileGenerator.exe")

        from app.extractor import to_wine_path
        cmd = [
            "wine", str(pfg_path),
            "-i", to_wine_path(input_pan),
            "-o", to_wine_path(output_pan),
            "-c", to_wine_path(changes_xml),
            "-b", str(device_id),
            "-n", device_name,
        ]

        import subprocess
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            logger.error(f"PFG failed: {result.stderr}")
            # Fall back to XML output
            final_xml = Path(output_dir) / f"{equipment_type}_changes.xml"
            shutil.copy2(changes_xml, final_xml)
            return str(final_xml)

        # Copy output to destination
        final_pan = Path(output_dir) / f"{equipment_type}.pan"
        shutil.copy2(output_pan, final_pan)
        logger.info(f"Generated .pan via PFG: {final_pan}")
        return str(final_pan)

    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def _to_library_format(assembly_result: dict, equipment_type: str, features: list) -> dict:
    """Convert assembler output to the library JSON format expected by generator.py.

    This format matches what the existing extractor produces from .pan files,
    so generator.py can consume it directly.

    Point names KEEP {device-name} placeholders.
    """
    objects = assembly_result.get('objects', {})
    code = assembly_result.get('code', '')
    io_map = assembly_result.get('io_map', {})

    library = {
        "id": f"composed_{equipment_type}_{'_'.join(sorted(features))}",
        "category": equipment_type,
        "format": "composed",
        "description": f"SBS {equipment_type} with {', '.join(features)}",
        "meta": {
            "composed": True,
            "equipment_type": equipment_type,
            "features": features,
            "modules": [m.get('id', '') for m in assembly_result.get('modules', [])],
            "io_counts": assembly_result.get('io_counts', {}),
        },
        "objects": {},
    }

    # Convert each object type to library format
    # Instance numbers are assigned sequentially per type
    for obj_type in ['AI', 'AO', 'AV', 'BI', 'BO', 'BV', 'MO', 'MV']:
        obj_list = objects.get(obj_type, [])
        if not obj_list:
            continue

        lib_points = []
        for i, obj in enumerate(obj_list, 1):
            point = {
                "name": obj.get('name', ''),
                "instance": str(i),
                "description": obj.get('desc', ''),
            }

            # Present value
            if obj.get('default') is not None:
                point["present_value"] = str(obj['default'])

            # Units
            if obj.get('units'):
                unit_enum = resolve_unit_enum(obj['units'])
                point["unit"] = str(unit_enum)

            # Min/max (range)
            if obj.get('min') is not None and obj.get('max') is not None:
                point["range"] = f"{obj['min']}"  # PFG uses range for min

            # States for binary/multistate
            if obj.get('states'):
                point["states"] = obj['states']

            lib_points.append(point)

        library["objects"][obj_type] = lib_points

    # Program object with Control-BASIC code
    if code.strip():
        library["objects"]["PROGRAM"] = [{
            "name": "{device-name}-PRG",
            "instance": "1",
            "description": f"Control program",
            "code": code,
            "enabled": True,
        }]

    # Schedule objects
    for obj in objects.get('SCHEDULE', []):
        if 'SCHEDULE' not in library["objects"]:
            library["objects"]["SCHEDULE"] = []
        library["objects"]["SCHEDULE"].append({
            "name": obj.get('name', ''),
            "instance": str(len(library["objects"]["SCHEDULE"]) + 1),
            "description": obj.get('desc', ''),
        })

    # Loop objects
    for obj in objects.get('LOOP', []):
        if 'LOOP' not in library["objects"]:
            library["objects"]["LOOP"] = []
        loop = {
            "name": obj.get('name', ''),
            "instance": str(len(library["objects"]["LOOP"]) + 1),
            "description": obj.get('desc', ''),
        }
        # PID params
        if obj.get('proportional') is not None:
            loop["proportional"] = str(obj['proportional'])
        if obj.get('integral') is not None:
            loop["integral"] = str(obj['integral'])
        library["objects"]["LOOP"].append(loop)

    return library


# ---------------------------------------------------------------------------
# Summary / reporting
# ---------------------------------------------------------------------------

def print_pan_summary(pan_structure: dict):
    """Print a human-readable summary of the pan-ready structure."""
    dev = pan_structure['device']
    print("=" * 72)
    print(f"  .PAN GENERATION SUMMARY")
    print(f"  Device: {dev['name']}  |  ID: {dev['device_id']}  |  "
          f"ObjID: 0x{dev['bacnet_objid']:08X}")
    print("=" * 72)

    # Controller
    ctrl = pan_structure.get('controller', {})
    if ctrl:
        model = ctrl.get('model', ctrl.get('summary', 'unknown'))
        print(f"\n  Controller: {model}")

    # Equipment / modules
    equip = pan_structure.get('equipment_type', '')
    modules = pan_structure.get('modules_loaded', [])
    print(f"  Equipment Type: {equip}")
    print(f"  Modules: {len(modules)}")
    for mod in modules:
        print(f"    [{mod.get('exec_order', 0):2d}] {mod.get('id', '')}")

    # Object summary
    obj_summary = pan_structure.get('object_summary', {})
    total = pan_structure.get('total_objects', 0)
    print(f"\n  BACnet Objects ({total} total):")
    for obj_type, count in sorted(obj_summary.items()):
        print(f"    {obj_type:10s}: {count}")

    # Object details
    print(f"\n  {'Type':<6} {'Inst':>4} {'Name':<40} {'Value':>8} {'Units':<15}")
    print(f"  {'---':<6} {'---':>4} {'---':<40} {'---':>8} {'---':<15}")

    for obj in pan_structure['objects']:
        obj_type = obj['type']
        inst = obj.get('instance', 0)
        name = obj['name']
        props = obj.get('properties', {})

        pv = props.get('present_value', {}).get('value', '')
        if isinstance(pv, float):
            pv_str = f"{pv:.1f}"
        else:
            pv_str = str(pv) if pv != '' else ''

        units_val = props.get('units', {}).get('value', 95)
        # Reverse lookup
        unit_name = 'no-units'
        for uname, uenum in UNIT_ENUMS.items():
            if uenum == units_val:
                unit_name = uname
                break

        print(f"  {obj_type:<6} {inst:>4} {name:<40} {pv_str:>8} {unit_name:<15}")

    # Loop refs
    loops = [o for o in pan_structure['objects'] if o['type'] == 'LOOP']
    if loops:
        print(f"\n  Loop Bindings:")
        for loop in loops:
            refs = loop.get('refs', {})
            print(f"    {loop['name']}:")
            for ref_key in ('input_ref', 'setpoint_ref', 'output_ref'):
                ref = refs.get(ref_key, {})
                if ref:
                    label = ref_key.replace('_ref', '').title()
                    print(f"      {label:10s}: {ref.get('name', 'N/A')} "
                          f"({ref.get('type', '?')}{ref.get('instance', '?')})")

    # I/O map
    io_map = pan_structure.get('io_map', {})
    if io_map:
        print(f"\n  I/O Terminal Map:")
        for terminal, point in sorted(io_map.items()):
            print(f"    {terminal:<8} -> {point}")

    # Code
    code_lines = pan_structure.get('code_lines', 0)
    print(f"\n  Control-BASIC: {code_lines} lines")

    # Warnings
    warnings = pan_structure.get('warnings', [])
    if warnings:
        print(f"\n  Warnings ({len(warnings)}):")
        for w in warnings:
            print(f"    ! {w}")

    print()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import sys

    if len(sys.argv) < 4:
        print("Usage: python3 -m app.modules.pan_generator <equipment_type> <features> <device_name> [device_id]")
        print()
        print("  equipment_type  Base type code (e.g., AHU-VAV, AHU-CV, FCU)")
        print("  features        Comma-separated feature codes (e.g., CHW,HW,ECON-DB,SF-VFD)")
        print("  device_name     Equipment tag (e.g., AHU-01)")
        print("  device_id       BACnet device instance (default: 1)")
        print()
        print("Example:")
        print("  python3 -m app.modules.pan_generator AHU-VAV CHW,HW,ECON-DB,SF-VFD,DSP,FREEZE,SMOKE,FLTR-DP AHU-01")
        sys.exit(1)

    equipment_type = sys.argv[1]
    features = [f.strip() for f in sys.argv[2].split(',')]
    device_name = sys.argv[3]
    device_id = int(sys.argv[4]) if len(sys.argv) > 4 else 1

    print(f"\nAssembling: {equipment_type} + [{', '.join(features)}]")
    print(f"Device: {device_name} (ID={device_id})")
    print()

    # Run assembler
    from app.modules.assembler import assemble, print_assembly_report

    try:
        result = assemble(
            equipment_type=equipment_type,
            features=features,
            device_name=device_name,
        )
    except Exception as e:
        print(f"Assembly failed: {e}")
        sys.exit(1)

    # Build pan structure
    pan_structure = build_pan_structure(result, device_name, device_id)

    # Print summary
    print_pan_summary(pan_structure)

    # Generate output
    output_path = generate_pan(
        assembly_result=result,
        device_name=device_name,
        device_id=device_id,
        output_dir="/tmp",
    )

    print(f"\nOutput: {output_path}")

    # Print quick assembly report too
    print("\n" + "=" * 72)
    print("  ASSEMBLY REPORT (from assembler)")
    print("=" * 72)
    print_assembly_report(result)
