# Taiko no Tatsujin Wii (JP) — game 1 (R2JJAF) findings  [taiko1.dol, ghydra port 8193]

Helper scripts live in <work-dir>/ :
  dol.py   - Dol(path): .v2o(addr) .o2v(off) .find(bytes) .d (raw bytes)
  dis.py   - `python3 dis.py N 0xLO 0xHI` big-endian PPC disassembly (taikoN.dol) via devkitPPC objdump
  fstarts.py - `python3 fstarts.py N 0xLO 0xHI` function prologue candidates (stwu r1 ... mflr)
  xr.py / xr2.py - lis/addi xrefs to an address
Ghidra's auto-analysis is shallow here (only ~1300 funcs), many functions are NOT defined, so
`functions_decompile` often fails: use memory_disassemble / dis.py instead.

## SDK layout (all addresses game 1)
- r2 = 0x80827ce0, r13 = 0x80825ac0 (set at 0x80004224)
- PADInit 0x800e79b0 (game DOES call it: 0x80033ce8 and 0x800324d4) -> SI auto-poll for GC pads is live
- WPAD lib ~0x80121000-0x80126400, KPAD lib ~0x80161e00-0x80165400
- WPADProbe = 0x801237fc (ch, &type) -> 0 ok / -1 none ; KPADRead = 0x801643a0 (ch, KPADStatus* buf(0x84 each), count)
- KPAD internal ring: per channel struct stride 0x538 at 0x80814458; samples 16 x 0x38 at +0x110
- KPAD button injection point (gbatemp guide "andi. r0,rX,0x9FFF"): 0x80162428 (func fn(kpad,devtype,cnt,r6=core btn,r7,r8=ext btn))

## Game input pipeline (game 1)
- Per-frame poll function: 0x80033e3c. For ch 0..3:
    KPADRead(ch, 0x806f89a0+ch*0x840, 16) -> count
    0x8016517c(ch, 0x806fab40+ch*0x230, count)   # copies 0x38-byte WPAD samples into game buffer (10 entries)
    WPADProbe(ch,&type) -> stores 0x806fabc0[ch] (ret) , 0x806faab0[ch] (type)
    0x800c7450(ch)  core-remote state maker  (hold -> 0x807b2220[ch], trig +0x10, rel +0x20, rep +0x30)
    0x800a5124(ch)  CLASSIC state maker (sample ext type==2 && fmt(+0x36)==7, buttons = ushort @sample+0x2a) -> 0x807948a0..
    0x800a4f28(ch)  TATACON state maker (ext type==0x13 && fmt==0x11, buttons ushort @+0x2a)            -> 0x80794840..
  Sample (0x38 B): +0 core btn(u16) +0x28 ext type(u8) +0x29 status(s8: 0 ok,-7 etc) +0x2a ext btn(u16) +0x36 data fmt
- Class Game::CTaikoPad (Pad.cc). Mapper `IsPressed(kind,ch,action,devflags)` = 0x800a5320 (3 tail-call wrappers:
  0x80049a94 trig(kind1), 0x8004a430 (kind3), 0x8004a44c hold(kind0)); ALL callers pass devflags=11 (core|classic|tatacon).
  Per-channel style selector table at 0x80794900+ch*0x14 (set by 0x800a574c(ch, coreStyle, clStyle, f2, f3, f4)).
  Gameplay drum faces = actions 0..3 with style from controller option (setControllerRemocon/Classic); menus use
  style (2,3,1,1,1) with actions: 0 left,1 right,2 decide,4 start,5 home,6 cancel.
- Action tables (r31 = 0x80211f08), row = 7 words (actions 0..6), 0x1c per style:
    core     @ +0x00 (5 styles)      bits: Wiimote btn (LEFT1 RIGHT2 DOWN4 UP8 PLUS10 TWO100 ONE200 B400 A800 MINUS1000 HOME8000)
    classic  @ +0x8c (5 styles)      bits: CL (UP1 LEFT2 ZR4 X8 A10 Y20 B40 ZL80 R200 PLUS400 HOME800 MINUS1000 L2000 DOWN4000 RIGHT8000)
    nunchuk? @ +0x118 (3)  (flag 4, unused by callers)
    tatacon  @ +0x16c (3 styles)  act0..3 = 0x40,0x10,0x20,0x08 (CL,RL,CR,RR; Dolphin TaTaCon: CENTER_L 0x40 RIM_L 0x10 CENTER_R 0x20 RIM_R 0x08)
    "dev4"   @ +0x1c0  (flag 0x10, channels 0/1 only, unused by callers)
  => actions 0..3 = don-L(center L), ka-L(rim L), don-R(center R), ka-R(rim R).
  core style0 (Wiimote sideways): LEFT|DOWN, ONE, RIGHT|UP, TWO. classic style0: dpad, face btns, L, R.
- Core hold maker 0x800c7450: final 16-bit hold in r7 right before 0x800c7520 (`slwi r11,r3,2`); r3=ch, r6=sample count
  (if r6==0 the old hold is re-used!). It is a leaf function (no LR save) -> hook with `b` not `bl`.
- Free DOL slots: DOL uses text sections 0,1 and data 7..14 -> text 2..6 and data 15..17 free. Low mem 0x80001820-0x80003000 free.
