"""
XML Generator for PFG
Takes a library JSON (from extraction) and generates a PFG-compatible changes XML.
PFG reads this XML and writes the points into a .pan file.

Usage:
    python3 generator.py <library_json> <output_xml> [--device-id 900] [--device-name "Office VAV"]

The generated XML uses PFG's exact format including the intentionally
malformed "log enabled" attribute that PFG expects.
"""

import json
import sys
import argparse
from pathlib import Path


def escape_xml_attr(s):
    """Escape a string for use in an XML attribute value."""
    return (str(s)
            .replace("&", "&amp;")
            .replace('"', "&quot;")
            .replace("<", "&lt;")
            .replace(">", "&gt;"))


def escape_xml_code(s):
    """Escape Control-BASIC code for embedding in <code> tags.
    PFG uses &gt; and &lt; inside code blocks."""
    return (str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;"))


def replace_device_name(name, device_name):
    """Replace {device-name} placeholder with actual device name."""
    if not name:
        return name
    return name.replace("{device-name}", device_name)


def build_point_attrs(point, device_name, device_id=None):
    """Build the attribute string for a point element."""
    attrs = []

    # Type is always first
    ptype = point.get("type", "")
    if ptype:
        attrs.append(f'type="{escape_xml_attr(ptype)}"')

    # Instance
    inst = point.get("instance", "")
    if inst:
        attrs.append(f'instance="{escape_xml_attr(inst)}"')

    # Present value (if exists)
    pv = point.get("present_value", "")
    if pv:
        attrs.append(f'presentValue="{escape_xml_attr(pv)}"')

    # Object name — replace {device-name} with actual
    name = replace_device_name(point.get("name", ""), device_name)
    if name:
        attrs.append(f'objectName="{escape_xml_attr(name)}"')

    # Description
    desc = point.get("description", "")
    attrs.append(f'description="{escape_xml_attr(desc)}"')

    return " ".join(attrs)


def generate_xml(library_data, device_id=None, device_name=None):
    """Generate PFG-compatible changes XML from library data.

    Args:
        library_data: dict from library JSON file
        device_id: BACnet device instance (e.g., "900"). If None, uses original.
        device_name: Device name for replacing {device-name} placeholders.
                     If None, leaves {device-name} in place.
    """
    objects = library_data.get("objects", {})

    if device_name is None:
        device_name = "{device-name}"

    lines = [
        '<?xml version="1.0" encoding="utf-8" standalone="yes"?>',
        '<points>',
    ]

    # ─── DEVICE ───
    for d in objects.get("DEVICE", []):
        did = device_id or d.get("instance", "")
        dname = device_name if device_name != "{device-name}" else d.get("name", "")
        dloc = d.get("location", "")
        lines.append(
            f'\t<point type="DEVICE" instance="{escape_xml_attr(did)}" '
            f'objectName="{escape_xml_attr(dname)}" '
            f'description="{escape_xml_attr(d.get("description", ""))}" '
            f'location="{escape_xml_attr(dloc)}"/>'
        )

    # ─── ANALOG / BINARY / MULTISTATE POINTS ───
    for ptype in ["AI", "AO", "AV", "BI", "BO", "BV", "MO", "MV"]:
        # Map back to PFG's full type names
        type_map = {
            "AI": "ANALOGINPUT", "AO": "ANALOGOUTPUT", "AV": "ANALOGVALUE",
            "BI": "BINARYINPUT", "BO": "BINARYOUTPUT", "BV": "BINARYVALUE",
            "MO": "MULTISTATEOUTPUT", "MV": "MULTISTATEVALUE",
        }
        full_type = type_map.get(ptype, ptype)

        for point in objects.get(ptype, []):
            name = replace_device_name(point.get("name", ""), device_name)
            attrs = [
                f'type="{full_type}"',
                f'instance="{escape_xml_attr(point.get("instance", ""))}"',
            ]
            if point.get("present_value"):
                attrs.append(f'presentValue="{escape_xml_attr(point["present_value"])}"')
            if name:
                attrs.append(f'objectName="{escape_xml_attr(name)}"')
            attrs.append(f'description="{escape_xml_attr(point.get("description", ""))}"')
            if point.get("range"):
                attrs.append(f'range="{escape_xml_attr(point["range"])}"')
            if point.get("increment"):
                attrs.append(f'increment="{escape_xml_attr(point["increment"])}"')
            if point.get("unit"):
                attrs.append(f'unit="{escape_xml_attr(point["unit"])}"')

            lines.append(f'\t<point {" ".join(attrs)}/>')

    # ─── LOOPS ───
    for loop in objects.get("LOOP", []):
        name = replace_device_name(loop.get("name", ""), device_name)
        attrs = [
            f'type="LOOP"',
            f'instance="{escape_xml_attr(loop.get("instance", ""))}"',
        ]
        if loop.get("present_value"):
            attrs.append(f'presentValue="{escape_xml_attr(loop["present_value"])}"')
        if name:
            attrs.append(f'objectName="{escape_xml_attr(name)}"')
        attrs.append(f'description=""')
        if loop.get("increment"):
            attrs.append(f'increment="{escape_xml_attr(loop["increment"])}"')
        if loop.get("derivative"):
            attrs.append(f'derivative="{escape_xml_attr(loop["derivative"])}"')
        if loop.get("deadband"):
            attrs.append(f'deadband="{escape_xml_attr(loop["deadband"])}"')
        if loop.get("integral"):
            attrs.append(f'integral="{escape_xml_attr(loop["integral"])}"')
        if loop.get("bias"):
            attrs.append(f'bias="{escape_xml_attr(loop["bias"])}"')
        if loop.get("action"):
            attrs.append(f'action="{escape_xml_attr(loop["action"])}"')
        if loop.get("proportional"):
            attrs.append(f'proportional-constant="{escape_xml_attr(loop["proportional"])}"')
        if loop.get("integralunits"):
            attrs.append(f'integralunits="{escape_xml_attr(loop["integralunits"])}"')

        lines.append(f'\t<point {" ".join(attrs)}/>')

    # ─── PROGRAMS ───
    for prog in objects.get("PROGRAM", []):
        name = replace_device_name(prog.get("name", ""), device_name)
        attrs = [
            f'type="PROGRAM"',
            f'instance="{escape_xml_attr(prog.get("instance", ""))}"',
        ]
        if name:
            attrs.append(f'objectName="{escape_xml_attr(name)}"')
        attrs.append(f'description="{escape_xml_attr(prog.get("description", ""))}"')

        code = prog.get("code", "")
        # Replace device name in code too
        code = code.replace("{device-name}", device_name)
        escaped_code = escape_xml_code(code)

        lines.append(f'\t<point {" ".join(attrs)}>')
        lines.append(f'\t\t<code>{escaped_code}')
        lines.append(f'</code>')
        lines.append(f'\t</point>')

    # ─── SCHEDULES ───
    for sched in objects.get("SCHEDULE", []):
        name = replace_device_name(sched.get("name", ""), device_name)
        attrs = [
            f'type="SCHEDULE"',
            f'instance="{escape_xml_attr(sched.get("instance", ""))}"',
        ]
        if sched.get("present_value"):
            attrs.append(f'presentValue="{escape_xml_attr(sched["present_value"])}"')
        if name:
            attrs.append(f'objectName="{escape_xml_attr(name)}"')
        attrs.append(f'description="{escape_xml_attr(sched.get("description", ""))}"')
        if sched.get("range"):
            attrs.append(f'range="{escape_xml_attr(sched["range"])}"')

        lines.append(f'\t<point {" ".join(attrs)}/>')

    # ─── CALENDARS ───
    for cal in objects.get("CALENDAR", []):
        name = replace_device_name(cal.get("name", ""), device_name)
        attrs = [
            f'type="CALENDAR"',
            f'instance="{escape_xml_attr(cal.get("instance", ""))}"',
        ]
        if cal.get("present_value"):
            attrs.append(f'presentValue="{escape_xml_attr(cal["present_value"])}"')
        if name:
            attrs.append(f'objectName="{escape_xml_attr(name)}"')
        attrs.append(f'description="{escape_xml_attr(cal.get("description", ""))}"')

        lines.append(f'\t<point {" ".join(attrs)}/>')

    # ─── TRENDS ───
    for trend in objects.get("TREND", []):
        name = replace_device_name(trend.get("name", ""), device_name)
        ttype = trend.get("type", "SINGLETREND")

        attrs = [
            f'type="{escape_xml_attr(ttype)}"',
            f'instance="{escape_xml_attr(trend.get("instance", ""))}"',
        ]

        # NOTE: Do NOT include "log enabled" attribute.
        # PFG writes "log enabled" (with a space) in its XML output, which is
        # invalid XML. PFG cannot read this attribute back — it causes
        # "error line 0 column 0". PFG defaults trends to enabled=true anyway.

        if name:
            attrs.append(f'objectName="{escape_xml_attr(name)}"')
        attrs.append(f'description="{escape_xml_attr(trend.get("description", ""))}"')
        if trend.get("interval"):
            attrs.append(f'interval="{escape_xml_attr(trend["interval"])}"')

        # Point references — replace device ID prefix if changing device
        refs = trend.get("references", [])
        for i, ref in enumerate(refs, 1):
            if ref:
                # References look like "4194293AI4" — replace old device ID
                if device_id:
                    # Strip old device ID prefix and rebuild
                    import re
                    m = re.match(r'\d+(.*)', ref)
                    if m:
                        ref = device_id + m.group(1)
                attrs.append(f'point{i}="{escape_xml_attr(ref)}"')

        if trend.get("logtype"):
            attrs.append(f'logtype="{escape_xml_attr(trend["logtype"])}"')

        lines.append(f'\t<point {" ".join(attrs)}/>')

    # ─── SMARTSENSORS ───
    for ss in objects.get("SMARTSENSOR", []):
        name = replace_device_name(ss.get("name", ""), device_name)
        attrs = [
            f'type="SMARTSENSOR"',
            f'instance="{escape_xml_attr(ss.get("instance", ""))}"',
        ]
        if name:
            attrs.append(f'objectName="{escape_xml_attr(name)}"')
        attrs.append(f'description="{escape_xml_attr(ss.get("description", ""))}"')

        lines.append(f'\t<point {" ".join(attrs)}/>')

    # ─── SYSTEMGROUPS ───
    for sg in objects.get("SYSTEMGROUP", []):
        name = replace_device_name(sg.get("name", ""), device_name)
        attrs = [
            f'type="SYSTEMGROUP"',
            f'instance="{escape_xml_attr(sg.get("instance", ""))}"',
        ]
        if name:
            attrs.append(f'objectName="{escape_xml_attr(name)}"')
        attrs.append(f'description="{escape_xml_attr(sg.get("description", ""))}"')
        if sg.get("groupgraphic"):
            attrs.append(f'groupgraphic="{escape_xml_attr(sg["groupgraphic"])}"')
        if sg.get("jsonpath"):
            attrs.append(f'jsonpath="{escape_xml_attr(sg["jsonpath"])}"')
        if sg.get("autoupdate"):
            attrs.append(f'autoupdate="{escape_xml_attr(sg["autoupdate"])}"')

        lines.append(f'\t<point {" ".join(attrs)}/>')

    lines.append('</points>')

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate PFG changes XML from library JSON")
    parser.add_argument("input_json", help="Path to library JSON file")
    parser.add_argument("output_xml", help="Path to write the changes XML")
    parser.add_argument("--device-id", help="BACnet device instance ID (e.g., 900)")
    parser.add_argument("--device-name", help="Device name (replaces {device-name} in point names)")
    args = parser.parse_args()

    data = json.loads(Path(args.input_json).read_text())

    xml = generate_xml(data, device_id=args.device_id, device_name=args.device_name)

    Path(args.output_xml).write_text(xml)
    print(f"Generated {args.output_xml}")
    print(f"  Points: {sum(len(v) for v in data.get('objects', {}).values() if isinstance(v, list))}")
    print(f"  Device ID: {args.device_id or 'original'}")
    print(f"  Device Name: {args.device_name or '{device-name}'}")


if __name__ == "__main__":
    main()
