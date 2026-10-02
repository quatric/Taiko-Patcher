# Taiko no Tatsujin Wii: Chou Goukaban (game 2, S5KJAF) - input pipeline  [taiko2.dol, ghydra port 8201]

Legend: CONFIRMED = traced in disassembly. GUESS = inferred / not run.
Helper scripts used: dis.py, fstarts.py (taiko/) plus g2lib.py (my own: calls(), lisrefs(), ptrs()).
Ghidra is NOT needed: all findings from raw DOL scans (Ghidra has 5779 funcs here, but I used dis.py).

## 0. Basics (CONFIRMED)
- entry 0x80006310. r2 = 0x8040c920 (lis/ori @0x8000654c/0x80006550), r13 = 0x80408ec0 (@0x80006554/0x80006558).
- DOL sections used: text0 0x80004000(0x2740), text1 0x80041120(0x2461a0), data7..14 (0x80006740 .. 0x80404920+0x1720). BSS 0x80403940 size 0xae5f0.
- Libs: KPAD ~0x801ec000-0x801f4b00 (KPADRead thunk 0x801ef990, real KPADReadEx 0x801ef9a0), PAD ~0x80207700-0x80208880 (PADInit 0x80208000),
  WPAD ~0x80216000-0x8021b000 (WPADInit 0x802184a0, WPADProbe 0x80219c00), WPADTko ~0x8024f000-0x80252xxx (only version string fn 0x80251580 found; game reads TaTaCon through the normal WPAD sample, see 2).
- THIS GAME HAS AN OOP PAD LAYER (classes IO::CPadCommon/CPadClassic/CPadDrum/CPadFreeStyle/CPadRemocon, strings @0x802a1368..0x802a1418) instead of game 1's 0x230-stride buffers.
  The "action table" layer is Game::CTaikoPad (string 0x8029d3f0, fn 0x80096f8c).

## 1. Per-frame poll (CONFIRMED)
- Main loop 0x800bb7d8: `0x800bb7e8: 4bfda991  bl 0x80096178` (words @0x800bb7e4: 48000024 4bfda991 4bf99121) -> poll function **0x80096178** once per frame.
  0x80096178 is non-leaf (stwu/mflr, saves r28-r31). SAFE bl call site to wrap (poll-level): **0x800bb7e8** (bl, non-leaf caller). Per-channel loop (r29 = ch 0..3, r30 = 0x804167e0):
    0x800961a4 bl OSDisableInterrupts(0x80200b70)
    0x800961c0  `481597d1 bl 0x801ef990`  = **KPADRead(ch, buf=0x804169a0+ch*0xF00, 16)** (words @0x800961b4: 7c9f0214 38a00010 481597d1); returns count in r3,
                 stored at 0x8041e1a0[ch] (r30+31168). KPADStatus here is 0xF0 bytes each x16 (stride 0xF00).
    0x800961d4 if count!=0: memcpy(0x8041a5a0+ch*0xF00, buf, 0xF00) via 0x80004000.  (accessor 0x800962b0(ch,idx) -> KPADStatus*, only used by CPadFreeStyle + 0x800b2778)
    0x8009620c bl 0x801f1520 = KPADGetUnifiedWpadStatus-like (ch, out=0x8041e240+ch*1056, count): copies up to count raw WPAD samples, 0x42 bytes each, from KPAD ring (stride 0x688 @0x804a8600). accessor 0x800962cc(ch).
    0x80096228  `481839d9 bl 0x80219c00` = **WPADProbe(ch, &type(r1+8))**; result stored 0x8041e1c0[ch] (r30+31200; read by getPadProbe 0x800b0838);
                 if result==0: type stored 0x8041e1b0[ch] (r30+31184; read by 0x8006a7bc(ch)); both default (type 253, probe 0) set at init 0x800960d0-0x800960e8.
    0x80096254/0x80096260/0x8009626c: update(obj,ch) for the 3 pad objects (see 3).
  Sample (0x42 B): +0 core btn u16, +0x28 ext type u8, +0x29 status s8 (0 ok,-7), +0x2a ext btn u16, +0x40 data format u8. (Game 1's 0x38 layout +0x36 fmt differs: here fmt at +0x40.)
- KPAD button-mask hook 0x801ec974 (`70c09fff andi. r0,r6,0x9fff`, words 81230000 70c09fff 28040001): function 0x801ec970 (r3=KPADStatus,r4=dev,r6=core btn,r7/r8 ext).
  CONFIRMED USELESS for this game's gameplay: the game reads Wii Remote/Classic/TaTaCon buttons from the unified WPAD samples (0x801f1520), NOT from KPADStatus.hold.
  KPADStatus.hold is used only by CPadFreeStyle (nunchuk Z/C, which is not queried in gameplay). Do not use this hook.

## 2. Gameplay drum hits (CONFIRMED)
Gameplay hit-collector = vtable method 0x8006a804 (vtable ptr @0x80029f50, caller 0x8006a6bc): for ch=this+0x10:
   styles = 0x800974d8(ch, remType=byte0 of option struct, clsType=byte1, 0,0,0)   [option struct = 0x800b6e60(); setRemoconType/setClassicType store bytes, no clamping]
   then 4x trig = 0x800973b0(ch, action 0..3, devflags=11) -> 4-bit mask: bit i = action i hit.  action 0..3 = don-L, ka-L, don-R, ka-R (by analogy with game 1; GUESS on face naming, CONFIRMED that they are the 4 gameplay actions).
IsPressed = **0x80096f8c(kind r3, ch r4, action r5, devflags r6)**; kind 0 hold / 1 trig / 2 release / 3 repeat. Wrappers: kind0 0x80097394, kind1 0x800973b0, kind3 0x800973cc, any-of-10 kind3 0x800973e8, kind2 0x80097460.
ALL 64 callers pass devflags=11 (core|classic|tatacon). flag 4 (nunchuk/CPadFreeStyle) and 0x10 (dev16, path disabled by stub 0x80096db0 = li r3,0) are never used. => NUNCHUK NOT SUPPORTED in gameplay/menus (CPadFreeStyle object is not even updated by the poll loop).
Device selection inside IsPressed: core path (flag 1) is evaluated ALWAYS (no ext-type test); classic path only if type[ch]==2, nunchuk if 1, tatacon if 0x13, where type = 0x8006a7bc(ch) (call @0x80097070: words 7f63db78 4bfd374d 28030002 41820018 28030001 418200c4 28030013).
Table row = 10 words (0x28 B), index = [0x8041f6f0 + ch*20 + devoff] (style), action = word index. Style words per channel (set by 0x800974d8: core +0, classic +4, nunchuk +8, tatacon +0xc, dev16 +0x10).
Tables (base r31 = 0x802a1438):
  CORE     0x802a1438, 8 rows. bits = Wii Remote core buttons (LEFT1 RIGHT2 DOWN4 UP8 PLUS10 TWO100 ONE200 B400 A800 MINUS1000 HOME8000)
     row0: 5 200 a 100 | 10 8000 0 ...   -> don-L=LEFT|DOWN  ka-L=ONE  don-R=RIGHT|UP  ka-R=TWO ; act4 PLUS act5 HOME   (DEFAULT, option value 0 -> sideways remote)
     row1: 9 100 6 200 | 10 8000
     row2: 9 6 900 0 | 10 8000 200 1000    (MENU style: 0 left=LEFT|UP, 1 right=RIGHT|DOWN, 2 decide=A|TWO, 4 PLUS, 5 HOME, 6 cancel=ONE, 7 MINUS)
     row3: 8 4 1 2 | 800 0 400 0 ;  row4: 200 100 8 4 | 10 8000 2 ;  row5: all 0 ;  row6: 9 6 100 0 | 10 8000 0 1000 800 200 ;  row7: 4 200 8 100 | 10 8000
  CLASSIC  0x802a1578 (= base+0x140), 8 rows. bits = Classic ext buttons (UP1 LEFT2 ZR4 X8 A10 Y20 B40 ZL80 R200 PLUS400 HOME800 MINUS1000 L2000 DOWN4000 RIGHT8000)
     row0 (default clsType 0): c003 78 2080 204 | 400 800     -> don-L = dpad (any of 4), ka-L = X|A|Y|B (78), don-R = L|ZL (2080), ka-R = R|ZR (204); PLUS start, HOME
     row1: c000 60 3 18 | 400 800 ; row2: 4002 50 8001 28 | 400 800 ; row3 (MENU): 2 8000 10 0 | 400 800 40 1000 (left=LEFT,right=RIGHT,decide=A,cancel=B)
     row4: 60 18 2082 8204 | 400 800 1 ; row5 zeros ; row6: 2002 8200 10 0 | 400 800 0 1000 8 20 ; row7: 8000 20 2080 204 | 400 800
  => CLASSIC CONTROLLER IS NATIVELY SUPPORTED in gameplay (and menus). No patch needed for Classic.
  NUNCHUK  0x802a16b8 (base+0x280) 3 rows (3 c 2000 4000 / 1 2 2000 ...): swing bits 1,2,4,8 + nunchuk Z 0x2000 C 0x4000 from CPadFreeStyle -> UNUSED (flag 4 never passed).
  TATACON  0x802a1730 (base+0x2f8), 6 rows, bits = TaTaCon ext buttons: CENTER_L 0x40, RIM_L 0x10, CENTER_R 0x20, RIM_R 0x08
     row0: 40 10 20 8 (=don-L, ka-L, don-R, ka-R)  <- gameplay style (tatacon style param = 0 in 0x8006a85c)
     row1: 20 8 50 0 ...  (MENU: 0 left=CENTER_R(0x20), 1 right=RIM_R(0x08), 2 decide=CL|RL (0x50))   row2: 40 10 20 8 ; row3: zeros ; row4: 20 8 50 ; row5: 40 10 20 8
  DEV16    0x802a1820 (base+0x3e8): disabled.
Style values passed to 0x800974d8 (core,classic,nunchuk,tatacon,dev): gameplay (opt remType, opt clsType,0,0,0) @0x8006a85c ; MENU (2,3,1,1,1) @0x800e52e8/0x8006ba70/0x8008764c ;
  (0,3,1,1,1) @0x800cd154 ; (6,6,1,4,1) @0x8005a014 ; (4,4,1,2,1) @0x800e5e5c ; (7,7,0,5,0) @0x800e5ab0 ; (?,?,0,?,0) @0x800e56ec.
Menu code 0x800e5310.. uses actions 0,1 (repeat), 2 (trig=decide), 6 (cancel), 4 (start), 7, flags 11.

## 3. Final hold word per channel (CONFIRMED)
All three live pad classes share ONE update function **CPadCommon::update(this=r3, ch=r4) = 0x800967d8** (called @0x80096254 core, 0x80096260 classic, 0x8009626c drum):
   objects (base 0x804167e0, constructors 0x800966c4/0x80096700/0x80096688/0x8009663c, vtable ptr at obj+0x68):
     CPadClassic  0x804167e0  vt 0x802a1378 (filter fn 0x80096914, getRaw 0x800969b4)  mask(+0x64)=0xc003
     CPadRemocon  0x8041684c  vt 0x802a1408 (filter 0x80096e0c, getRaw 0x80096ea4)     mask 0xf
     CPadDrum     0x804168b8  vt 0x802a13a8 (filter 0x80096a70, getRaw 0x80096a78)     mask 0
     CPadFreeStyle 0x80416924 vt 0x802a13d8 (getRaw 0x80096b3c) mask 0   -- NEVER UPDATED
   per object layout: hold[4] @+0x00 (u32 per ch), trig @+0x10, release @+0x20, repeat @+0x30, counters +0x40/+0x50, sticky flag +0x60+ch, mask +0x64, vtable +0x68.
   (IsPressed getters read exactly these arrays, e.g. 0x80096540 core hold, 0x8009656c core trig, etc.)
   update code (words in 0x800967d8: 9421ffe0 7c0802a6 90010024 39610020 480e6029 7c7b1b78 7c9c2378 81830068 818c000c 7d8903a6 4e800421 547e043e):
     0x800967e8 bl 0x8017c810 (savegpr_27); r27 = this, r28 = ch
     0x800967f4 lwz r12,104(r3); lwz r12,12(r12); mtctr; **0x80096800 bctrl** = getRaw(this,ch) -> r3 = raw 16-bit hold (class specific)
     **0x80096804: 547e043e  clrlwi r30,r3,16**   <-- BEST HOOK: raw hold in r3, this in r27, ch in r28; r30 must receive result
     0x80096808.. r31 = ch*4, r29 = old hold = stored[ch]&0xffff, r0=mask(+0x64)
     0x80096824 and r5,r30,r0 ; and r6,r29,r0 ; vcall slot 8 = filter(this,ch,new&mask,old&mask) -> r3
     0x80096838 801b0064 7fc00078 7c600378 **0x80096844: 7c1bf92e stwx r0,r27,r31** (r0 = final hold = (raw & ~mask) | filtered) ; then trig = (hold^old)&hold -> +0x10, rel -> +0x20.
   The function is NOT a leaf: LR is saved @0x800967e0 and bl/bctrl are used, so `bl hook` at 0x80096804 is fine (LR is dead there; return to 0x80096808).
   Registers at 0x80096804: live: r27 (this), r28 (ch), r1; r30 is the output; r29 and r31 are loaded AFTER (0x80096808/0x80096810) so they are free scratch; r0, r3-r12 volatile and free (r12/ctr dead).
   Wrapper contract: in r3 = raw; out r30 = (r3 & 0xffff) with GC bits OR-ed; r3 may be anything after (r3 reloaded @0x8009681c).
   Alternative: 0x80096844 (`stwx r0,r27,r31`, words 801b0064 7fc00078 7c600378 7c1bf92e) with r0 = final hold, r27/r28/r31 available; r3,r4 are recomputed afterwards.
 *** STALE-BIT HAZARD (CONFIRMED): when the sample count is 0 (no Wii Remote / no new samples) each getRaw RE-USES the stored old hold (Remocon 0x80096f54-0x80096f64: cmpwi r29,0; bne; lwzx r0,r30,(ch<<2); clrlwi r28,r0,16; Classic 0x80096a38; Drum 0x80096afc). If the stored hold contains injected GC bits, they would never be cleared.
     => in the hook keep a shadow word shadow[obj][ch] of the last injected bits: r30 = ((raw & ~shadow) | newGC) & 0xffff ; shadow = newGC.  (Negative count => getRaw returns 0: harmless.)
   Design recommendation for GC pad / DK Bongo (no Wiimote needed):
     * CPadDrum object (0x804168b8) bits 0x40 (don-L) 0x10 (ka-L) 0x20 (don-R) 0x08 (ka-R): works for all 4 faces in gameplay (tatacon style 0) AND for menu left/right/decide (style 1 uses 0x20 left, 0x08 right, 0x50 decide).
       REQUIRES type[ch]==0x13 (see 4) because IsPressed only consults the tatacon table when 0x8006a7bc(ch)==0x13.
     * CPadRemocon object (0x8041684c) for non-drum buttons: PLUS 0x10 (start/pause in all gameplay core rows 0,1,4,6,7), HOME 0x8000, MINUS 0x1000, A 0x800 / B 0x400 / ONE 0x200 (menu: decide=A|TWO(0x900), cancel=ONE 0x200). Core path needs NO type spoof. Dpad bits are filtered by 0x80096e0c and also map to gameplay hits in core rows; avoid injecting dpad unless wanted for menus.
     * Menu cancel with only drum bits is impossible (tatacon menu row has no cancel) -> use Remocon ONE (0x200, core menu row2 act6) or Classic B (0x40, row3).

## 4. PADInit / WPADProbe / connection gating
- PADInit = **0x80208000** (CONFIRMED; idempotent via flag r13-18896). Game DOES call it: @0x80095fec (right after KPADInit 0x801f01b0 @0x80095fe8, in init fn 0x80095fb8) and @0x800ba810 (fn at 0x800ba7e8-ish). => SI auto-poll for GC pads is live (GUESS: PADRead never called by game, PAD reset state machine runs from SI callbacks).
  PADRead: not called by the game. Candidates 0x80207920 / 0x802079e0 (memset 12-byte PADStatus per channel via 0x80004350; GUESS) - better read SI regs directly or verify in Dolphin. (SIC0INBUFH 0xCD006404+ch*12; GUESS)
- WPADInit = 0x802184a0 (@0x80095fe4). WPADProbe = **0x80219c00**(ch,&type): returns *(ch struct+0x900) (-1 if none), *type = ext type byte (+0x905). Table of WPAD ch structs: 0x804a3db0.
  Game WPADProbe call sites: **0x80096228 (poll; main one)**, 0x800b2750 (separate per-channel pointer/status object, probe at this+ch*4, type this+0x10+ch*4; used by pointer UI 0x800b25cc), 0x801efa3c/0x801f0b4c/0x801f333c (inside KPAD lib), others in WPAD/Tko libs.
- Gating (CONFIRMED structure):
   * IsPressed/update themselves contain NO connection check - bits are bits. Nothing in the hit path stops a player without a Wii Remote, except: (a) core/Drum getRaw return old hold with 0 samples (so no new bits), (b) the type gate for classic/tatacon tables (type[ch]), (c) script-level checks.
   * Script bindings: getPadProbe (name @0x802eb400 -> fn 0x800eaad8 -> 0x800b0838(ch) = 0x8041e1c0[ch]); getPadType (name 0x802eb40c -> fn 0x800eab34): requires probe==0 then maps type: 0->1, 2->3, 0x13->2, 1->1(?), 0xfb etc: see 0x800eab90-0x800eac38. Menus/join screens use these to decide if a slot is a valid player (GUESS about exact join logic).
   * Disconnect detector fn 0x800b0758 (called @0x800b067c): per ch if getPadProbe(ch)==0 sets connected flag this+0x38+ch; later if flag && probe==-1 -> bit in this+0x28 (=> pause/"reconnect controller" UI, GUESS).
- Candidate patch sites to spoof "connected" (all CONFIRMED to exist; behaviour GUESS until tested):
   S1 (best, covers probe+type for scripts, disconnect detector AND IsPressed): replace `bl 0x80219c00` @**0x80096228** (word 481839d9) by `bl wrapper`: call real WPADProbe; if r3!=0 (no Wii device) and GC pad / bongo present for r29(ch): store 0x13 to *(r1+8)... precisely: wrapper(r3=ch, r4=&type): real = WPADProbe(ch,r4); if (real!=0 && gc[ch]) {*r4 = 0x13 (TaTaCon) ; real = 0;} return real. (the caller stores r3 to 0x8041e1c0[ch] and, since r3==0, the type from r1+8 to 0x8041e1b0[ch].) Also then WPAD ext type 0x13 makes getPadType return 2 (TaTaCon).
   S2 (if a real Wiimote may coexist): replace `bl 0x8006a7bc` @**0x80097070** (word 4bfd374d; r3=ch) -> wrapper returns 0x13 when GC input active on ch else real type.
   S3: patch 0x800b0838 (leaf: slwi r0,r3,2 / lis / addi / lwzx / blr) to return 0 for GC players.
   S4: poll-level hook @0x800bb7e8 (bl 0x80096178) to read PAD/SI once per frame into a global before the update loop runs.

## 5. Free space (CONFIRMED by DOL header)
- Text sections 2-6 (idx 2..6) have size 0 / addr 0 -> FREE (5 slots). Data sections 15,16,17 free (size 0). (Used: text 0,1; data 7..14.)
- Low memory 0x80001820..0x80003000: no DOL section there and no lis 0x8000 / base-0 absolute refs found in the code scan (hits with imm 0x206e/0x1e3c.. were false positives: 0xCC00xxxx hardware regs / struct offsets). OS globals are touched only at 0x80003000+ (0x80003xxx). FREE (GUESS only for runtime/loader: nothing in this DOL touches it).
- BSS 0x80403940-0x804b1f30; game's own tables start ~0x804167e0 (pad objs) -> 0x8041f6f0 (style table, 20 B/ch); placing shadow vars in low-mem or new text/data sections is preferable.

## Summary
- Poll: 0x80096178 (call site 0x800bb7e8); KPADRead call 0x800961c0; WPADProbe call 0x80096228.
- Buttons come from unified WPAD samples (0x42 B, 0x8041e240+ch*0x420), not KPADStatus; the 0x801ec974 hook is irrelevant.
- Classic native (tables row0: dpad/XAYB/L,ZL/R,ZR). TaTaCon native (0x40,0x10,0x20,0x08). Nunchuk not supported.
- One common update fn 0x800967d8 for classic/remocon/drum objects; hook at 0x80096804 (`clrlwi r30,r3,16`) with this=r27, ch=r28; need shadow to avoid stale bits.
- Inject GC pad into the CPadDrum object (type spoof to 0x13 via WPADProbe wrapper at 0x80096228) + Remocon bits for start/cancel.
