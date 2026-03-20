"""
SBS Composition Engine v2 — CBAS Decompiler

Decompiles Reliable Controls CBAS bytecode back to .bas source code.
Reverse of cbas_compiler.py.
"""

import struct
import re

# Type decode map
TYPE_DECODE = {
    b'\x00\x00\x00': 'AI', b'\x00\x00\x01': 'AO', b'\x00\x80\x00': 'AV',
    b'\x00\xc0\x00': 'BI', b'\x01\x00\x00': 'BO', b'\x00\x40\x01': 'BV',
    b'\x00\xc0\x04': 'MV', b'\x00\x80\x03': 'MO', b'\x00\x00\x03': 'LOOP',
}

SLOT_TO_VAR = {i+2: chr(ord('A')+i) for i in range(26)}

FUNC_DECODE = {
    0x5d: 'LIMIT', 0x37: 'MAX', 0x38: 'MIN', 0x3f: 'AVG',
    0x33: 'ABS', 0xda: 'SELECT', 0x42: 'ENTHALPY', 0x43: 'SLIDE',
    0x44: 'SWITCH', 0x45: 'RAMP', 0x46: 'TIME-ON', 0x47: 'TIME-OFF',
    0x4a: 'SCHED', 0x4b: 'INTERVAL',
}

OP_DECODE = {
    0x6b: '+', 0x6c: '-', 0x67: '*', 0x68: '/',
    0x6d: '>', 0x6e: '<', 0x6f: '>=', 0x70: '<=',
    0x71: '<>', 0x65: '=', 0x73: 'AND', 0x74: 'OR', 0x72: 'NOT',
}


def decompile(bytecode: bytes) -> str:
    """Decompile CBAS bytecode to .bas source."""
    lines = []
    i = 0

    while i < len(bytecode):
        if bytecode[i] == 0x01 and i + 2 < len(bytecode):
            line_num = bytecode[i+1] + (bytecode[i+2] << 8)
            if 1 <= line_num <= 9999:
                i += 3

                # REM line
                if i < len(bytecode) and bytecode[i] == 0x00 and i+1 < len(bytecode) and bytecode[i+1] == 0x1a:
                    i += 2
                    text_start = i
                    while i < len(bytecode) and bytecode[i] != 0x02:
                        i += 1
                    text = bytecode[text_start:i].decode('ascii', errors='replace')
                    lines.append(f"{line_num} REM {text}")
                    if i < len(bytecode): i += 1
                    continue

                # Code line
                expr_stack = []
                store_target = None

                while i < len(bytecode) and bytecode[i] != 0x09:
                    b = bytecode[i]

                    if b == 0xc3 and i + 4 < len(bytecode):
                        inst = bytecode[i+1]
                        tn = TYPE_DECODE.get(bytes(bytecode[i+2:i+5]), '??')
                        store_target = f"{tn}{inst}"
                        i += 5
                    elif b == 0xc2 and i + 4 < len(bytecode):
                        inst = bytecode[i+1]
                        tn = TYPE_DECODE.get(bytes(bytecode[i+2:i+5]), '??')
                        expr_stack.append(f"{tn}{inst}")
                        i += 5
                    elif b == 0x9d and i + 4 < len(bytecode):
                        val = struct.unpack('<f', bytecode[i+1:i+5])[0]
                        expr_stack.append(str(int(val)) if val == int(val) else f"{val:.6g}")
                        i += 5
                    elif b == 0xa3 and i + 2 < len(bytecode):
                        store_target = SLOT_TO_VAR.get(bytecode[i+2], f'VAR{bytecode[i+2]}')
                        i += 3
                    elif b == 0x82 and i + 2 < len(bytecode):
                        expr_stack.append(SLOT_TO_VAR.get(bytecode[i+2], f'VAR{bytecode[i+2]}'))
                        i += 3
                    elif b in OP_DECODE:
                        op = OP_DECODE[b]
                        if len(expr_stack) >= 2:
                            right = expr_stack.pop()
                            left = expr_stack.pop()
                            expr_stack.append(f"{left} {op} {right}")
                        i += 1
                    elif b in FUNC_DECODE and i + 1 < len(bytecode):
                        fn = FUNC_DECODE[b]
                        argc = bytecode[i+1]
                        args = [expr_stack.pop() for _ in range(min(argc, len(expr_stack)))]
                        args.reverse()
                        expr_stack.append(f"{fn}( {' , '.join(args)} )")
                        i += 2
                    elif b == 0xff:
                        expr_stack.append("END")
                        i += 1
                    else:
                        i += 1

                if store_target and expr_stack:
                    lines.append(f"{line_num} {store_target} = {expr_stack[-1]}")
                elif expr_stack:
                    lines.append(f"{line_num} {' '.join(expr_stack)}")

                if i < len(bytecode) and bytecode[i] == 0x09: i += 1
                continue
        i += 1

    return '\n'.join(lines)
