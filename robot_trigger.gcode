; RoboFab Robot Trigger Test
G91 ; Relative positioning
G1 Z10 F3000 ; Lift nozzle 10mm up
G90 ; Absolute positioning

; Move to Back-Left (Top-Left) Parking Spot
; Sovol SV08 Bed is ~350x350
G1 X10 Y340 F6000 

G4 P2000 ; Wait for 2 seconds (simulating finish)
; End of file