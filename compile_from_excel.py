#!/usr/bin/env python3
"""Compile .pan directly from SBS v2 Excel package."""
import struct, zipfile, re, sys
from io import BytesIO
from openpyxl import load_workbook

sys.path.insert(0, '/srv/reliable-generator-dev')
from composition.pan_compiler import (
    write_av_block, write_ai_block, write_bi_block, write_bo_block,
    write_ao_block, write_bv_block, write_mv_block, write_loop_block,
    write_program_block, write_schedule_block, write_sys_group_block,
    write_trend_block, write_nc_group_block, write_device_block_from_blank,
    crc16_kermit, _require_unit, _parse_default,
    _write_index_entry, _read_blank_header, UNIT_CODES
)
from composition.models import ValuePoint, InputPoint, OutputPoint, LoopDef
from composition.cbas_compiler import compile_bas

PKG = "/srv/dfa/drops/sbs-full-package (4).zip"
BLANK = "/srv/dfa/shared/files/vendors/reliable/blanks/MACH-ProSys-88/MACH-ProSys-88.panx"
OUT = "/srv/dfa/drops/SBS-AHU-VAV-COMPILED.pan"

# Read Excel
with zipfile.ZipFile(PKG) as z:
    wb = load_workbook(BytesIO(z.read("RC-Studio-Output.xlsx")), read_only=True)
    bas_files = {n.split("/")[-1]: z.read(n).decode() for n in z.namelist() if n.endswith(".bas")}

def rs(name):
    rows = list(wb[name].iter_rows(values_only=True))
    for i, row in enumerate(rows):
        if sum(1 for c in row if c is not None) >= 3:
            hdr = [str(c).strip() if c else "" for c in row]
            return [dict(zip(hdr, r)) for r in rows[i+1:] if any(v is not None for v in r)]
    return []

# Build name→ObjID lookup
n2o = {}
for r in rs("Inputs"):
    if r.get("Name"):
        n2o[str(r["Name"])] = (0 if str(r.get("Type","AI"))=="AI" else 3, int(r["Terminal"]))
for r in rs("Outputs"):
    if r.get("Name"):
        n2o[str(r["Name"])] = (1 if str(r.get("Type","AO"))=="AO" else 4, int(r["Terminal"]))
for r in rs("Values"):
    if r.get("Name"):
        n2o[str(r["Name"])] = ({"AV":2,"BV":5,"MV":19}.get(str(r.get("Type","AV")),2),
                                int(re.sub(r'[^0-9]','',str(r.get("Instance","0")))))

def res(pn):
    if pn in n2o:
        t, i = n2o[pn]
        return (t << 22) | (i & 0x3FFFFF)
    return 0xFFFFFFFF

# Build blocks
bt = {}
bt[15] = [write_nc_group_block(0,"System",0x0D),
          write_nc_group_block(1,"General",0x0D),
          write_nc_group_block(65,"Trend",0x0E)]

ai = []; bi = []
for r in rs("Inputs"):
    if not r.get("Name"): continue
    n, t, pt = str(r["Name"]), int(r["Terminal"]), str(r["Type"])
    d, u = str(r.get("Description","") or ""), str(r.get("Units","") or "")
    if pt == "AI":
        ai.append(write_ai_block(InputPoint(row=t, name=n, point_type="AI", range_code="", description=d, units=u)))
    elif pt == "BI":
        bi.append(write_bi_block(InputPoint(row=t, name=n, point_type="BI", range_code="", description=d)))
if ai: bt[0] = ai
if bi: bt[3] = bi

ao = []; bo = []
for r in rs("Outputs"):
    if not r.get("Name"): continue
    n, t, pt = str(r["Name"]), int(r["Terminal"]), str(r["Type"])
    d, u = str(r.get("Description","") or ""), str(r.get("Units","") or "") or "%"
    if pt == "AO":
        ao.append(write_ao_block(OutputPoint(row=t, name=n, point_type="AO", range_code="", description=d, units=u)))
    elif pt == "BO":
        bo.append(write_bo_block(OutputPoint(row=t, name=n, point_type="BO", range_code="", description=d)))
if ao: bt[1] = ao
if bo: bt[4] = bo

av = []; bv = []; mv = []
for r in rs("Values"):
    if not r.get("Name"): continue
    n = str(r["Name"])
    inst = int(re.sub(r'[^0-9]', '', str(r.get("Instance", "0"))))
    pt = str(r.get("Type", "AV"))
    dv = r.get("Default Value", 0)
    u = str(r.get("Units", "") or "")
    d = str(r.get("Description", "") or "")
    if pt == "AV":
        av.append(write_av_block(ValuePoint(instance=inst, name=n, point_type="AV", default=dv, description=d, units=u)))
    elif pt == "BV":
        bv.append(write_bv_block(ValuePoint(instance=inst, name=n, point_type="BV", default=dv, description=d)))
    elif pt == "MV":
        mv.append(write_mv_block(ValuePoint(instance=inst, name=n, point_type="MV", default=dv, description=d)))
if av: bt[2] = av
if bv: bt[5] = bv
if mv: bt[19] = mv

lp = []
for r in rs("Loops"):
    if not r.get("Name"): continue
    inst = int(re.sub(r'[^0-9]', '', str(r.get("Loop", "0"))))
    nm = "{device-name}-" + str(r["Name"])
    ir, sr = str(r.get("Input","") or ""), str(r.get("Setpoint","") or "")
    act = "reverse" if str(r.get("Action", "+")) == "-" else "direct"
    loop = LoopDef(instance=inst, name=nm, input_ref=ir, setpoint_ref=sr, output_ref="",
                   p_band=float(r.get("P Band",0) or 0), integral=float(r.get("Integral",0) or 0), action=act)
    loop._input_objid = struct.pack('>I', res(ir))
    loop._setpoint_objid = struct.pack('>I', res(sr))
    lp.append(write_loop_block(loop))
if lp: bt[12] = lp

prg = []
for r in rs("Programs"):
    if not r.get("Name"): continue
    inst = int(re.sub(r'[^0-9]', '', str(r.get("PRG#", "0"))))
    nm, fn = str(r["Name"]), str(r.get("Filename","") or "")
    code = bas_files.get(fn, "")
    bc = b""
    if code:
        try:
            bc = compile_bas(code)
        except Exception as e:
            print(f"  PRG{inst} compile error: {e}")
    prg.append(write_program_block(inst, nm, bc))
if prg: bt[16] = prg

sc = []
for r in rs("Schedules"):
    if not r.get("Name"): continue
    sc.append(write_schedule_block(1, str(r["Name"])))
if sc: bt[17] = sc

sg = []
for r in rs("System Groups"):
    if not r.get("Name"): continue
    sg.append(write_sys_group_block(1, str(r["Name"])))
for r in rs("Tables"):
    if not r.get("Name"): continue
    inst = int(re.sub(r'[^0-9]', '', str(r.get("Table", "0"))))
    nm, ou = str(r["Name"]), str(r.get("Output Units","") or "")
    xy = []
    for line in str(r.get("Data Points","") or "").split("\n"):
        if "→" in line:
            parts = line.split("→")
            try: xy.append((float(parts[0].strip()), float(parts[1].strip())))
            except: pass
    sg.append(write_sys_group_block(inst, "{device-name}-" + nm,
              unit_code=_require_unit(ou, nm), table_data=xy))
if sg: bt[141] = sg

tr = []
for r in rs("Trends"):
    if not r.get("Name"): continue
    inst = int(re.sub(r'[^0-9]', '', str(r.get("STL", "0"))))
    nm, mp = str(r["Name"]), str(r.get("Monitored Point","") or "")
    buf = int(r.get("Buffer", 512) or 512)
    tr.append(write_trend_block(inst, name=nm, monitored_objid=res(mp), buffer_size=buf))
if tr: bt[20] = tr

bt[8] = [write_device_block_from_blank(BLANK)]

# Build file
type_order = [15, 0, 1, 2, 3, 4, 5, 8, 12, 14, 16, 17, 19, 20, 26, 27, 141]
pres = [t for t in type_order if t in bt]
nt = len(pres)
bs = 0x0400 + nt * 0x40 + 6

tof = {}; co = bs
for tid in pres:
    tof[tid] = co
    for blk in bt[tid]:
        co += len(blk)

db = bt[8][0]
doi = struct.unpack_from('>I', db, 6)[0] & 0x3FFFFF
bh = _read_blank_header(BLANK)

fd = bytearray()
h = bytearray(12)
struct.pack_into('<I', h, 0, 0x0023BAC0)
struct.pack_into('<I', h, 4, doi)
struct.pack_into('<I', h, 8, bh[2])
fd += h
fd += bytes(0x400 - 12)

for idx, tid in enumerate(pres):
    fd += _write_index_entry(nt if idx == 0 else 0, tid, tof[tid], len(bt[tid]))
    fd += bytes(0x40 - 16)
fd += bytes(6)

for tid in pres:
    for blk in bt[tid]:
        fd += blk

pan = bytes(fd)
with open(OUT, "wb") as f:
    f.write(pan)

# Verify
def ri(d, o):
    v = []
    for i in range(4):
        h2 = struct.unpack_from('<H', d, o+i*4)[0]
        l = struct.unpack_from('<H', d, o+i*4+2)[0]
        v.append((h2 << 16) | l)
    return v

TYPES = {0:'AI',1:'AO',2:'AV',3:'BI',4:'BO',5:'BV',8:'DEV',12:'LOOP',15:'NC',16:'PRG',17:'SCH',19:'MV',20:'TREND',141:'SYS'}
first = ri(pan, 0x400)
ok = 0; tot = 0
pos = first[2]
for j in range(first[3]):
    sz = struct.unpack_from('<H', pan, pos)[0]; t2 = sz + 2
    if crc16_kermit(pan[pos+12:pos+t2]) == struct.unpack_from('>H', pan, pos+10)[0]: ok += 1
    tot += 1; pos += t2
for i in range(1, first[0]):
    e = ri(pan, 0x440 + (i-1) * 0x40)
    pos = e[2]
    for j in range(e[3]):
        if pos + 12 > len(pan): break
        sz = struct.unpack_from('<H', pan, pos)[0]; t2 = sz + 2
        if pos + t2 > len(pan): break
        if crc16_kermit(pan[pos+12:pos+t2]) == struct.unpack_from('>H', pan, pos+10)[0]: ok += 1
        tot += 1; pos += t2
    print(f"  {TYPES.get(e[1],'?'):4s} count={e[3]:3d}")

print(f"\n{len(pan)}B, {tot} blocks, CRC: {ok}/{tot}")
print(f"Ready: {OUT}")
