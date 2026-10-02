# Taiko no Tatsujin Wii: Ketteiban (game 4, STJJAF) findings  [taiko4.dol, ghydra port 8205 (not needed, all traced via scripts on the raw DOL)]
Tools used: dol.py, dis.py, bl.py (bl-caller scan, new, <work-dir>/bl.py), dd.sh (compact dis), xr2.py.
Tags: CONFIRMED = traced in code, GUESS = inferred.

## Summary of how game 4 differs from game 1
Same architecture as game 1 (KPADRead + KPAD "unified WPAD" ring copy + per-device-class state objects + IsPressed mapper with
action tables), but reorganised into C++ classes (RTTI names: IO::CPadCommon / CPadClassic / CPadDrum / CPadFreeStyle / CPadRemocon,
vtable-based). There is NO 0x230 buffer, NO "setControllerClassic" strings (those are Lua-ish script binding names: setRemoconType /
getClassicType at 0x802a9e68..). Classic Controller IS natively supported in gameplay (CONFIRMED). Nunchuk (CPadFreeStyle) exists but is dead code.
SDK: r2 = 0x803cf9c0, r13 = 0x803cc280 (lis/ori at 0x8000654c/0x80006554, CONFIRMED).
DOL sections: text0 0x80004000/0x2740, text1 0x80036ea0/0x20dae0, data7 0x80006740 data8 0x80022480 data9 0x80244980 data10 0x80244b20
data11 0x80244b40 data12 0x80258600 (0x16bc80) data13 0x803c4280 data14 0x803c79c0; BSS 0x803c6900..0x80471f70.

## Library addresses (CONFIRMED)
- KPADInit 0x801ad9d0 ; KPADRead(ch,buf,n)=0x801ad1b0 (tail-falls into KPADReadEx 0x801ad1c0, r6=r7=0); KPAD ch struct stride 1672 (0x688) at 0x8045(?)-0x7ac0 ; KPADStatus size 0xF0 (240!), 16 entries/ch.
- KPAD per-sample builder (andi. r0,r6,0x9FFF) fn at 0x801aa190 (leaf, r3=KPADStatus, r4=devtype, r6=core btn, r8=ext btn): word 0x801aa194 = 70c09fff.
  KPADStatus: +0 hold(u32) +4 trig +8 rel ; ext (classic/nunchuk) hold +0x60 trig +0x64 rel +0x68 ; callers 0x801ad63c, 0x801ad7dc.
- KPAD "unified WPAD status" reader = 0x801aed40(ch, buf, n): copies 66-byte (0x42) samples (game 1 equivalent: 0x8016517c with 0x38 B).
  66-B sample: +0 core btn u16, +0x28 (40) ext type u8, +0x29 (41) status s8 (0 ok), +0x2a (42) ext btn u16, +0x40 (64) ext data fmt u8.
  (classic: type 2 fmt 7; TaTaCon: type 0x13 fmt 0x11 -- identical to game 1)
- WPADProbe(ch,&type) = 0x801d7420 (entry words 9421fff0 7c0802a6 3ca08046). Returns 0 ok / -1 none, writes type byte to *r4 ALWAYS (also on failure).
- PADInit = 0x801c5820 (CONFIRMED: refs PAD version string at 0x801c5840, ends with PADReset(0xF0000000)=0x801c5600).
  Game DOES call it: 0x8007c5f8 (inside the pad init 0x8007c5c4, right after KPADInit 0x8007c5f4) and 0x800a0b88 (system init).
  PAD lib is stripped: nothing but PADInit (+internals) is referenced; the game never calls PADRead -> GC pad data must be read via SI regs
  (0xCD006400 + ch*12: INBUFH/INBUFL; status 0xCD006438) or by your own PAD code. SI auto-poll is started by PADInit's reset chain (GUESS: PAD reset will only
  enable polling for standard GC pads; a DK Bongo might need your own SISetCommand/SIEnablePolling).
- WPADTko lib (version string 0x803c3a18) code ~0x8020eb..0x8021ee: not touched by the input path (the game uses plain KPAD/WPAD and the "TaTaCon" ext type 0x13).

## 1. Per-frame poll (CONFIRMED)
- Main-loop function 0x800a1b50: `loop: bl 0x8007c784 (pad poll); bl 0x8004a47c; bl 0x80081298; bl 0x800a16e0; bl 0x800a1ba8; bl 0x800a17a0; bl 0x801d0f70`
  The call site to redirect: **0x800a1b60: `bl 0x8007c784` = 0x4bfdac25** (file off 0x6d500). Surrounding function 0x800a1b50 is non-leaf (stwu/mflr), so replace it with `bl wrapper`; wrapper = call 0x8007c784 then do GC/bongo polling and fill the state (see below). 0x8007c784 has exactly ONE caller.
- Poll function 0x8007c784 (stwu 9421ffe0 / mflr 7c0802a6 / stw r0,36(r1) 90010024). Loop ch=0..3 (r29), r30 = 0x803d8d20 (state base `B`):
    0x8007c7b0 bl 0x801be390 (OSDisableInterrupts)
    0x8007c7cc `bl 0x801ad1b0` = 0x481309e5 : KPADRead(ch, B+448+ch*3840 = 0x803d8ee0+ch*0xF00, 16) -> count, stored to B+31168 = 0x803E06E0[ch]
         (count may be 0 or NEGATIVE error; it is nonzero-tested only)
    if count!=0: memcpy(B+15808+ch*3840 = 0x803dcae0+ch*0xF00, kpadbuf, 3840)   (persistent "last read" buffer, KPADStatus[16]x240; accessor 0x8007c8bc(ch,idx))
    0x8007c818 bl 0x801aed40(ch, B+31328+ch*1056 = 0x803E0780+ch*0x420, count)   (unified 66-B samples, 16 per ch; accessor 0x8007c8d8(ch); count accessor 0x8007c8a8(ch))
    0x8007c834 `bl 0x801d7420` = 0x4815abed : WPADProbe(ch, sp+8) ; init sp+8 = 253 (0xFD)
    0x8007c840 `stwx r3,r4,r5` : probe result -> B+31200 = 0x803E0700[ch]; if result==0 then type -> B+31184 = 0x803E06F0[ch] (read by 0x800603d8(ch); read of ret by 0x80096cc4(ch))
    0x8007c858/0x8007c864/0x8007c870 : `bl 0x8007cde4(obj,ch)` for objects B+108 (Remocon), B+0 (Classic), B+216 (Drum)   [B+324 FreeStyle(Nunchuk) is NOT updated: dead]
- Alternative earlier hook inside the poll: after 0x8007c818 (r29=ch live) or at the probe call 0x8007c834 (see 4.).

## 2. Gameplay drum hits (CONFIRMED structure)
### State objects (size 108, in BSS at B=0x803d8d20; vtable ptr at +104; hold[4] +0, trig[4] +16, rel[4] +32, repeat-cnt +48/+64/+80, "repeat mask" +100)
 | obj addr | class (vtable) | mask(+100) | hold getter (vtbl+12) | filter (vtbl+8) |
 | 0x803d8d20 | CPadClassic   0x8025dd20 | 0xC003 (set 0x8007c73c)| 0x8007cfc0 | 0x8007cf20 |
 | 0x803d8d8c | CPadRemocon   0x8025ddb0 | 0x000F | 0x8007d4b0 | 0x8007d418 |
 | 0x803d8df8 | CPadDrum      0x8025dd50 | 0 | 0x8007d084 | 0x8007d07c |
 | 0x803d8e64 | CPadFreeStyle 0x8025dd80 | 0 | 0x8007d148 (core hold & 0x6000 | stick bits) | 0x8007d140 | (never updated => Nunchuk unsupported)
 Update function 0x8007cde4(obj,ch): new = vtbl[3](obj,ch) (16-bit); old=obj[ch]; hold=(new&~mask)|vtbl[2](...repeat filter); trig=(hold^old)&hold; rel=(hold^old)&old.
 Accessors (ch, -1): Classic hold/trig/rel/rep 0x8007c93c/c968/c994/c9c0; Drum 0x8007c9ec/ca18/ca44/ca70; FreeStyle 0x8007ca9c..cb20; Remocon 0x8007cb4c/cb78/cba4/cbd0.
 Hold getters: Classic: OR of ushort@sample+0x2a over samples with status==0,type==2,fmt==7. Drum: type 0x13, fmt 0x11. Remocon: OR of ushort@sample+0 over samples with status==0 or -7.
 If sample count==0 (or the count is <0 : the cmpwi r,0 test only catches 0; negative => result 0) the OLD hold is reused (0 samples) for Classic/Drum/Remocon (hold <- obj[ch]).
### Mapper IsPressed(kind, ch, action, devflags) = 0x8007d598   (entry words 9421ffd0 7c0802a6)
 kind: 0 hold, 1 trig, 2 release, 3 repeat. Tail-call wrappers: hold 0x800502a0 (kind0), trig 0x8005098c (kind1), repeat 0x8006ca74 (kind3); loops "any" 0x800c94a4(kind3) / 0x800c95dc(kind2).
 ALL 45 direct callers pass devflags = 11 = core(1)|classic(2)|tata(8) (scanned; flag 4 = nunchuk and 0x10 = "dev4" never passed).
 Per flag: result |= (stateobj.kind[ch] & table[style][action]) != 0
   flag 1 : Remocon obj, ALWAYS evaluated (no device-type check)
   flag 2 : Classic obj, only if devtype(ch)==2   (devtype = 0x803E06F0[ch], getter 0x800603d8)
   flag 4 : FreeStyle obj, only if devtype==1 (unused)
   flag 8 : Drum obj, only if devtype==0x13
   flag 0x10: "dev4" 0x8007d3bc.. only ch 0/1 (unused)
 Style selector table: 0x803E1C30 + ch*20 : [+0]=core style [+4]=classic [+8]=nunchuk [+12]=tata(drum) [+16]=dev4 ; setter 0x8007d9b0(ch,core,classic,nun,tata,dev4)
 Action tables: base T=0x8025dde0, ROW = 40 bytes = 10 words (actions 0..9), table[style*40 + action*4]:
   core     T+0x000 (0x8025dde0) 7 styles (rows 0..6)
   classic  T+0x118 (0x8025def8) 7 styles (rows 0..6)   (r31+280)
   nunchuk  T+0x230 (0x8025e010) 3 styles               (r31+560)
   tata     T+0x2a8 (0x8025e088) 5 styles               (r31+680)
   dev4     T+0x370 (0x8025e150) 3 styles               (r31+880)
 Actions 0..3 = don-L, ka-L, don-R, ka-R. Menus: 0 left,1 right,2 decide,3 (up/-),4 start(+),5 home,6 cancel,7 minus.
 Core bits (WPAD): LEFT1 RIGHT2 DOWN4 UP8 PLUS10 TWO100 ONE200 B400 A800 MINUS1000 HOME8000.
 Classic bits (CL as in game 1): UP1 LEFT2 ZR4 X8 A10 Y20 B40 ZL80 R200 PLUS400 HOME800 MINUS1000 L2000 DOWN4000 RIGHT8000.
 Tata bits: 0x40 center-L, 0x10 rim-L, 0x20 center-R, 0x08 rim-R.
 Core rows (act0..7):  s0: 5,200,a,100,10,8000,0,0   s1: 9,100,6,200,10,8000  s2(menu): 9,6,900,0,10,8000,200,1000  s3: 8,4,1,2,800,0,400  s4: 8,4,900,0,10,8000,2  s6: 9,6,100,0,10,8000,0,1000,800,200
 Classic rows: s0: c003(all dpad),78(A|B|X|Y),2080(L|ZL),204(R|ZR),400,800 ; s1: c000,60,3,18 ; s2: 4002,50,8001,28 ; s3(MENU): 2(L),8000(R),10(A),0,400,800,40(B cancel),1000 ; s4: 2,8000,10,0,400,800,1,0 ; s5 zeros; s6: 2002,8200,10,0,400,800,0,1000,8,20
 Tata rows: s0 (GAMEPLAY): 40,10,20,08 ; s1 (menu): 20,08,50 ; s2: 20,08,50 ; s3: zeros ; s4: 20,08,50
 Nunchuk rows (unused): s0: 3,c,2000,4000
 => Gameplay style source: the per-frame sampler **0x80060420** (called from 0x800602d8 inside the 3-frame-history object, ch = obj+16) does
        0x80060478 bl 0x8007d9b0 with (ch, byte0(core opt), byte1(classic opt), 0, 0, 0)  [raw word 0x4801d539, setStyle call]
        then trig-kind(1) IsPressed(ch, action 0..3, 11) at 0x80060490/0x800604a4/0x800604b8/0x800604cc (words 4bff04fd ... via 0x8005098c), result bits 0..3 = hits.
    => in gameplay: core style = player option (0..6), classic style = player option (0..6), TATA STYLE = 0 (row 0x8025e088: 40,10,20,08).
    A second style setter 0x800c8d00 (virtual method 0x800c8c90) uses (core opt, classic opt, 0, tata=byte3 of player data, 0) -- GUESS: used by option/other screens.
    Menu styles: (core 2, classic 3, nun 1, tata 1, dev4 1) from 0x800c88fc/0x80061624/0x8006d180 ; title screen 0x8004f774: (6,6,1,4,1). Gameplay detection for a hook: tata style word 0x803E1C3C+ch*20 == 0 (GUESS but consistent with code).
 Native support: Wii Remote YES; **Classic Controller YES (CONFIRMED)** with the classic rows above (style default = player option; style0 = dpad/face/L/R); TaTaCon YES (needs devtype==0x13); Nunchuk NO (object never updated; flag 4 never passed).

## 3. Final 'core hold' injection (differs from game 1: virtual-method per class, all non-leaf)
Hold maker hooks (replace the final `mr r3,rX` before the epilogue; all three functions are non-leaf, LR saved at 36(r1), so `bl hook` is safe; r0, r3-r12 free):
 - Remocon  0x8007d4b0 : **0x8007d574 `mr r3,r28` = 0x7f83e378** ; r28 = final hold (16 bit), r31 = ch, r29 = sample count, r30 = obj. Previous insn 0x8007d570 `clrlwi r28,r0,16` (old-hold path when count==0).
 - Classic  0x8007cfc0 : **0x8007d058 `mr r3,r30` = 0x7fc3f378** ; r30 = hold, r29 = ch, r31 = count, r28 = obj
 - Drum     0x8007d084 : **0x8007d11c `mr r3,r30` = 0x7fc3f378** ; r30 = hold, r29 = ch, r31 = count, r28 = obj
 Because old hold is re-used when count==0, never OR into a variable that persists; recompute: `if (count<=0 (or channel is GC-owned)) r3 = gcbits else r3 = r30|gcbits`.
 This avoids stuck bits.
 Alternative single hook point in the common update fn: 0x8007ce10 `clrlwi r30,r3,16` (0x547e043e) right after the `bctrl` of vtbl[3] (r27=obj, r28=ch, r3=new hold) -- covers all objects (differentiate by r27).
 Alternative lowest level: KPAD 0x801aa194 (hold of KPADStatus) -- not recommended here (unified-sample path is what the game reads).
### Best design for a GC-pad / DK Bongo player (proposal)
 a) Make the game treat ch as a TaTaCon: spoof WPADProbe at the poll call 0x8007c834 (see 4.) returning 0 and type 0x13.
 b) Drum hook 0x8007d11c : r3 = gc drum bits (0x40 don-L, 0x10 ka-L, 0x20 don-R, 0x08 ka-R), independent of player options (tata gameplay style 0 is fixed!). For DK Bongo: left bongo -> 0x40 (don-L), right -> 0x20, clap -> 0x10/0x08.
    Drum-menu rows give: left=0x20, right=0x08, decide=0x50 (so D-pad L / D-pad R / A also work as menu nav through the same hook in menus).
 c) For full menus (up/down, cancel, +, home): inject into Remocon hold at 0x8007d574 using core MENU style 2 (9 left/up, 6 right/down, 0x900 decide, 0x200 cancel, 0x10 start, 0x8000 home)
    BUT only when tata-style word [0x803E1C3C+ch*20] != 0 (i.e. not in gameplay), otherwise core style (player option) rows would also turn dpad/buttons into extra hits.
## 4. PADInit / WPADProbe / connection spoof
 PADInit 0x801c5820 (calls: 0x8007c5f8, 0x800a0b88), WPADProbe 0x801d7420 (game calls: 0x8007c834 and 0x80098c94; lib-internal: 0x801ad25c 0x801ae36c 0x801b0b5c ...).
 "Connected" = WPADProbe ret==0 stored at 0x803E0700[ch] (getter 0x80096cc4 -> -1 means no controller; used by 0x80096be4 player-disconnect mask and 0x800cd3b0/0x800cd40c controller UI), and devtype 0x803E06F0[ch] (253 initial; 0 core, 1 nunchuk, 2 classic, 19 tata, 251 = ?).
 Spoof site: **0x8007c834 `bl 0x801d7420` (0x4815abed)** (non-leaf function, r29=ch before the call: args r3=ch r4=sp+8): replace by `bl wrapper`, wrapper = real WPADProbe; if ret!=0 and GC pad present on ch -> `*r4 = 0x13; r3 = 0` (r3 is then stored at 0x8007c840 and the type at 0x8007c84c-0x8007c854 because ret==0).
 Second probe site 0x80098c94 (0x4813e78d) belongs to the pointer/cursor object (0x80098c64) -> leave alone.
 Note KPAD itself (lib-internal WPADProbe) still reports the channel as absent; hold makers see count<=0 -> that is why the hooks must replace, not OR.
 Setting devtype to 0 instead of 0x13 makes only the Remocon path active (player-option dependent rows); 0x13 is the recommended spoof.

## 5. Free space (CONFIRMED from DOL header + low-mem scan)
 DOL uses text 0,1 and data 7..14 only => text slots 2..6 and data slots 15..17 free (header sizes 0). No code loads/stores 0x80001800..0x80002fff (lis 0x8000 + low imm scan) => low mem 0x80001820..0x80003000 free. Largest hits are OS globals at 0x80003000+ (0x30e4..0x30f4).
 BSS ends at 0x80471f70 (0x803c6900 + 0xab670).

## Hook raw words summary (file offset in DOL)
 0x800a1b60 4bfdac25 (bl 0x8007c784, foff 0x6d500) | 0x8007c7cc 481309e5 (KPADRead call, foff 0x4816c) | 0x8007c834 4815abed (WPADProbe, foff 0x481d4)
 0x8007d574 7f83e378 (foff 0x48f14) | 0x8007d058 7fc3f378 (foff 0x489f8) | 0x8007d11c 7fc3f378 (foff 0x48abc) | 0x8007ce10 547e043e (foff 0x487b0)
 0x80060478 4801d539 setStyle in gameplay (foff 0x2be18) | 0x801aa194 70c09fff (foff 0x175b34)
