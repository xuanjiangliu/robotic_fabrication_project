; --- FGF CONTINUOUS EXTRUSION TEST (STATIONARY) ---
; Duration: Approx 5 Minutes
; Temp: 200C
; Flow: 100%
; MOVEMENT: NONE (Extrudes at current position)

; 1. SAFETY & SETUP
M106 S255       ; Turn FAN1 (Throat Cooling) to 100%
M221 S100       ; Set Flow Rate to 100%
M83             ; Relative Extrusion Mode (Critical for this loop)

; 2. HEATING
M117 Heating to 200C...
M109 S200       ; Set Nozzle to 200C and WAIT

; 3. EXTRUSION LOOP
M117 Extruding...

; --- Block 1 (Minute 1) ---
G1 E50 F300     ; Extrude 50mm @ 300mm/min
G1 E50 F300
G1 E50 F300
G1 E50 F300
G1 E50 F300
G1 E50 F300

; --- Block 2 (Minute 2) ---
G1 E50 F300
G1 E50 F300
G1 E50 F300
G1 E50 F300
G1 E50 F300
G1 E50 F300

; --- Block 3 (Minute 3) ---
G1 E50 F300
G1 E50 F300
G1 E50 F300
G1 E50 F300
G1 E50 F300
G1 E50 F300

; --- Block 4 (Minute 4) ---
G1 E50 F300
G1 E50 F300
G1 E50 F300
G1 E50 F300
G1 E50 F300
G1 E50 F300

; --- Block 5 (Minute 5) ---
G1 E50 F300
G1 E50 F300
G1 E50 F300
G1 E50 F300
G1 E50 F300
G1 E50 F300

; 4. FINISH
M117 Test Complete.
M104 S0         ; Turn off Heater
M221 S100       ; Reset Flow Rate to 100%
; Fan stays on to prevent heat creep clogs.