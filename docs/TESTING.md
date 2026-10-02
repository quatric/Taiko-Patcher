# Test status

Method (tools/gtest.py): build a patched image with wit, boot it in Dolphin with a virtual GameCube pad
(Dolphin "Pipe" input), attach Dolphin's GDB stub and read both the payload's state and the game's *own*
input state arrays while pressing buttons. Dolphin 2609-7, macOS.

| game | pad detected + shown as TaTaCon | buttons reach the game's state | notes |
|---|---|---|---|
| 1 Taiko Wii | yes | **yes, all** (A/B/X/Y/L/R/Z/Start, D-pad, left stick, C-stick) | probe = 0, type = 0x13 |
| 2 Chou Goukaban | yes | not verified | emulator input was not delivered / run was killed |
| 3 Dodoon | yes | not verified | same |
| 4 Ketteiban | not verified | not verified | emulator was killed (memory pressure / another Dolphin on the machine) |
| 5 Minna de Party 3 | not verified | not verified | same |

Games 2-5 are patched through one shared hook (`CPadCommon::update`) that is byte-identical in all four
DOLs; its register use was checked in the disassembly, but it has not yet been exercised with real input.
Not tested: real hardware, DK Bongos (detection logic only), multi-player, Wii Remote + GC pad on one port.
