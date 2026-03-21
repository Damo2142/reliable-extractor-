# SBS Controls — VAV Integration Standard
## Composer / Compiler Project Reference

---

## OVERVIEW

This document defines the SBS standard for VAV-to-AHU data integration.
It supersedes the legacy array-based approach and establishes the new
direct-write BACnet architecture as the SBS standard going forward.

Both methods must be supported in the Composer and compiler.

---

## METHOD 1 — NEW SBS DIRECT WRITE (preferred for all new jobs)

### Concept

VAV boxes write data directly to the AHU controller using BACnet
peer-to-peer writes. No parent/router controller needed. No arrays needed.
The AHU is set as the {parent} of the VAV template at commissioning.

### How it works

```
VAV template writes directly to {parent} AV instances:
  {parent}AV17  = room temperature
  {parent}AV18  = cooling demand
  {parent}AV19  = heating requests
  {parent}AV111 = zone damper position
  {parent}AV112 = NSB mode
  {parent}AV113 = NSF mode
  {parent}AV114 = bypass mode
  {parent}AV115 = setpoint deviation

AHU template reads its own local AV instances:
  AV17  = high room temp (calculated)
  AV18  = avg room temp (calculated)
  AV19  = low room temp (calculated)
  etc.
```

### Commissioning — one step only

```
Tech sets {parent} = AHU BACnet device ID
That is the entire VAV-to-AHU configuration.
No box numbers. No AHU numbers. No manual arrays.
```

### Stagger timing — prevents trunk flooding

```
Each VAV staggers its writes based on its own device ID:

write_offset = (DEV1000:1042 MOD 30) * 2 seconds
update_interval = 60 seconds

This spreads 30 VAV writes across 60 seconds.
No trunk coordination needed between VAVs.
No synchronized writes. Self-managing.

For trim and respond: 60 second update is more than adequate.
For zone temp averaging: 30-60 seconds is fine per ASHRAE G36.
For heating/cooling demand: 1 minute is sufficient.
RC-FLEXair Linux/multicore handles this easily.
```

### Why this is better than the legacy approach

```
Eliminated:
  Parent/router controller module
  Array objects AY1-AY8
  Zone array processing program
  Router program
  BOX-# AV value
  AHU-# AV value
  Manual box number entry
  Manual AHU number entry

BACnet was designed for peer-to-peer direct writes.
This is the correct use of the protocol.
Direct writes across MS/TP trunk are not a performance
problem on modern controllers (RC-FLEXair, MPS, MPC).
Staggered timing eliminates any residual load concern.
```

### Composer template pairing

```
Engineer selects in Composer:
  AHU type  → e.g. AHU-VAV-HTG-CLG
  VAV type  → e.g. VAV-SDR (single duct reheat)

Composer generates matched template pair:
  AHU pan file — defines AV17-AV119 locally
  VAV pan file — writes to {parent} AV17-AV119
  Template pair guarantees AV instance compatibility
  No manual cross-referencing needed
```

---

## METHOD 2 — LEGACY ARRAY METHOD (retain for existing jobs)

### Concept

VAV boxes write data to arrays in a parent/router controller.
The parent processes the array data and stores results in specific
AV instances. The AHU reads those AV instances from the parent.

### Data flow

```
RC-FLEXair VAV:
  Writes raw data to parent arrays each scan:
  {parent}AY1[box#] = room temp
  {parent}AY2[box#] = cooling demand
  {parent}AY3[box#] = heating request
  {parent}AY4[box#] = damper position
  {parent}AY5[box#] = NSB mode
  {parent}AY6[box#] = NSF mode
  {parent}AY7[box#] = bypass mode
  {parent}AY8[box#] = setpoint deviation

Parent controller (MPS/MPC):
  Zone array program reads arrays and calculates:
  AV17  = high room temp   (MAX of AY1)
  AV18  = avg room temp    (AVG of AY1)
  AV19  = low room temp    (MIN of AY1)
  AV111 = max cooling demand (MAX of AY2)
  AV112 = total heating requests (SUM of AY3)
  AV113 = max damper position (MAX of AY4)
  AV114 = total zones served
  AV115 = total bypass requests (SUM of AY7)
  AV116 = total NSB requests (SUM of AY5)
  AV117 = total NSF requests (SUM of AY6)
  AV118 = high setpoint deviation (MAX of AY8)
  AV119 = low setpoint deviation (MIN of AY8)

AHU:
  Reads AV17-AV119 from parent by instance number
  Uses for reset strategies and trim & respond
```

### Legacy array instance map (LOCKED — never change)

```
Array objects in parent controller:
  AY1 = {device-name}-AHU{n}-RMT-AY       (room temps)
  AY2 = {device-name}-AHU{n}-CLG-DMD-AY   (cooling demand)
  AY3 = {device-name}-AHU{n}-HTG-REQ-AY   (heating requests)
  AY4 = {device-name}-AHU{n}-DMP-POS-AY   (damper positions)
  AY5 = {device-name}-AHU{n}-NSB-MODE-AY  (NSB mode)
  AY6 = {device-name}-AHU{n}-NSF-MODE-AY  (NSF mode)
  AY7 = {device-name}-AHU{n}-BYP-MODE-AY  (bypass mode)
  AY8 = {device-name}-AHU{n}-SP-DEV-AY    (setpoint deviation)

Result AV instances in parent (LOCKED):
  AV16  = master first-on time
  AV17  = high room temp
  AV18  = avg room temp
  AV19  = low room temp
  AV111 = max cooling demand
  AV112 = total heating requests
  AV113 = max damper position
  AV114 = total zones
  AV115 = total bypass requests
  AV116 = total NSB requests
  AV117 = total NSF requests
  AV118 = high setpoint deviation
  AV119 = low setpoint deviation
```

### Manual configuration required per job

```
Each VAV requires:
  BOX-#  = zone address (1-127), set manually in RC Studio
  AHU-#  = which AHU this VAV serves, set manually
  {parent} = parent controller device ID
```

---

## LOCKED AV INSTANCE MAP — BOTH METHODS

These AV instances are identical in both methods.
The AHU program always reads these same instance numbers.
NEVER change these instance numbers.

```
AV16  = master first-on time
AV17  = high room temp
AV18  = avg room temp
AV19  = low room temp
AV111 = max cooling demand
AV112 = total heating requests
AV113 = max zone damper position
AV114 = total zones served
AV115 = total bypass requests
AV116 = total NSB requests
AV117 = total NSF requests
AV118 = high setpoint deviation
AV119 = low setpoint deviation
```

---

## FACTORY FIXED POINTS — DO NOT CONFLICT

### RC-FLEXair (all models — confirmed from blank .panx files)

```
AI4  = {device}-VP          Velocity pressure (differential pressure)
AI5  = {device}-DMP-POS     Damper position
BI6  = {device}-DMP@END     Damper at end of travel
BO8  = {device}-CW-CLS      Damper clockwise to close

User-defined I/O must NOT use AI4, AI5, BI6, BO8.
User inputs start at AI1, AI2, AI3 (avoid AI4, AI5).
User binary inputs avoid BI6.
User binary outputs avoid BO8.
```

### MACH-ProView LCD (all models — confirmed from blank .panx files)

```
AI7   = TEMPERATURE
AI8   = HUMIDITY
BI9   = OCCUPANCY
AI10  = (unnamed — reserved)

User-defined I/O must NOT use AI7, AI8, AI9, AI10.
Also has factory AV values — see factory_points_proview.txt
```

### MACH-ProAir (legacy — for reference)

```
AI1  = VP (velocity pressure — onboard sensor)
AI2  = flow sensor
AO1  = damper actuator (onboard)
Flow and motor control algorithms hard-coded in firmware.
```

---

## COMPOSER MODULE STRUCTURE

### New job (direct write method)

```
Modules generated:
  1. AHU module (MPS/MPC)
     - Full AHU control sequences
     - AV17-AV119 defined locally
     - Reads zone data from own AV instances

  2. VAV module (RC-FLEXair)
     - VAV control sequences
     - Writes directly to {parent} AV instances
     - Staggered timing via device ID
     - {parent} set at commissioning = AHU device ID
```

### Legacy job (array method)

```
Modules generated:
  1. AHU module (MPS/MPC)
     - Full AHU control sequences
     - Reads AV17-AV119 from parent

  2. Parent/router module (MPS/MPC)
     - Array objects AY1-AY8
     - Zone array processing program
     - Router program
     - Stores results in AV17-AV119

  3. VAV module (RC-FLEXair or MACH-ProAir)
     - VAV control sequences
     - Writes to {parent} array elements
     - Uses BOX-# and AHU-# (manual entry required)
```

---

## MIGRATION PATH

```
Existing legacy jobs:
  Keep array method — do not break working systems

New jobs:
  Always use direct write method

Legacy job retrofit:
  When programming is updated swap to direct write
  No hardware change needed
  Remove array program from VAV
  Add direct write program to VAV
  Set {parent} = AHU device ID
  Remove parent/router module if no longer needed
```

---

## NOTE ON MSTP ADDRESSING

```
Reliable Controls recommends MSTP device addresses
match physical location on the trunk.
SBS position: this is a legacy recommendation
from 1990s hardware that does not apply to
modern controllers (RC-FLEXair, MPS v8+).

Address assignment should follow project needs
not physical trunk order.
RC-FLEXair with Linux/multicore is not impacted
by non-sequential MSTP addressing.
```

---

## FOR CLAUDE CODE

When building VAV Composer modules:

```
1. Generate TWO VAV program variants:
   - Direct write version (new standard)
   - Array write version (legacy support)
   Composer selects based on job type setting.

2. AV17-AV119 instance numbers are LOCKED.
   Never assign other points to these instances
   in any AHU or parent controller module.

3. RC-FLEXair factory points AI4, AI5, BI6, BO8
   must be preserved from blank .panx file.
   Never overwrite with user-defined points.

4. MACH-ProView factory points AI7, AI8, BI9, AI10
   must be preserved from blank .panx file.

5. Stagger timing formula for direct write VAV:
   offset = (DEV1000:1042 MOD 30) * 2 seconds
   interval = 60 seconds
   Implement in VAV write program.

6. {parent} placeholder in VAV programs
   is set by tech at commissioning = AHU device ID.
   It is NOT set by the compiler.
   Compiler writes {parent} as a placeholder.
```
