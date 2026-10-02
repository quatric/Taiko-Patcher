# Taiko Wii: Minna de Party 3-daime! (S3TJAF) - game 5 input findings  [taiko5.dol, ghydra 8207]

Marks: CONFIRMED = traced in code (dis.py/ghidra bytes), GUESS = inferred.
Game 5 is NOT like game 1. It is a C++ class design (RTTI strings IO::CPadCommon/CPadClassic/CPadDrum/CPadFreeStyle/CPadRemocon
at 0x80226580..0x80226630). Sample buffers are 66-byte (0x42) "unified WPAD status" entries, not 0x230-stride.

r2 = 0x80378180, r13 = 0x80374ae0 (set at 0x80006550/0x80006558)   CONFIRMED

## SDK function addresses (CONFIRMED unless noted)
- KPADRead(ch, KPADStatus* buf, count)  = 0x8017c3b0 (li r6,0;li r7,0; b 0x8017c3c0). KPADStatus stride 0xF0, 16 entries (3840 B/ch)
- KPADGetUnifiedWpadStatus / "WPADRead" (ch, out66*, count) = 0x8017df40 ; copies newest-first 0x42-byte samples from WPAD ring
- WPADProbe(ch, &type) = 0x801a6000   (0 ok / -1 none ; type written only if ok)
- PADInit = 0x80194580 (version slot ref at 0x801945a0 `lwz r3,-23184(r13)`; SIInit/PAD lib ~0x80191700-0x80194d30).
  Game DOES call it: 0x80094100 and 0x8006dc5c (inside pad-init 0x8006dc28 <- 0x80094160). So SI polling for GC pads is live.
  PADRead/PADClamp were NOT located (no external callers of any PAD function; PADRead is probably dead-stripped) -> a GC patch must
  bring its own SI read (e.g. read SIC0INBUF at 0xCD006400+12*ch after PADInit's polling enabled) - GUESS.
- KPAD button mask `andi. r0,r6,0x9FFF` = 0x80179394 (word 70c09fff) exists but is IRRELEVANT for drum input: the game reads the unified
  WPAD samples (0x8017df40) for core/classic/tatacon; KPAD copy is only used by the (dead) nunchuk path. Do not hook it.
- memcpy = 0x80004000 ; memset = 0x80004350 ; OSDisableInterrupts = 0x8018d590 ; OSRestoreInterrupts = 0x8018d5d0

## 1. Per-frame poll
Main loop function 0x800950d0 (frame 16, LR saved). Loop body 0x800950e0:
    800950e0: 4bfd8d09  bl 0x8006dde8        <- PER-FRAME POLL (once per frame; bl site is safe to redirect, non-leaf, no args)
    800950e4: bl 0x80036e54 ...  (then ... bl 0x8019fcd0 = frame wait)
Poll function 0x8006dde8 (stwu r1,-32; saves r28-r31). r30 = 0x80381300 (pad manager base). For ch=r29 in 0..3 (always 4 channels):
    8006de14 bl OSDisableInterrupts
    8006de30: 4810e581 bl 0x8017c3b0   KPADRead(ch, 0x803814c0+ch*0xF00, 16) -> count; stored 0x80388cc0[ch]  (stwx at 0x8006de3c)
    8006de5c  if count!=0: memcpy(0x803850c0+ch*0xF00, kpadbuf, 0xF00)     (KPAD copy; accessor 0x8006df20(ch,idx) = 0x803850c0+ch*3840+idx*240)
    8006de7c: 481100c5 bl 0x8017df40   unified WPAD samples (ch, 0x80388d60+ch*1056, count)   (accessor 0x8006df3c(ch); count accessor 0x8006df0c(ch))
    8006de98: 48138169 bl 0x801a6000   WPADProbe(ch, r1+8)       <- best site to spoof "controller connected"
    8006dea4: 7c64292e stwx r3,r4,r5   probe ret -> 0x80388ce0[ch]  (accessor 0x80089ec4(ch); 0 = connected, -1 = disconnected)
    8006deac-8006deb8: if ret==0: type (r1+8) -> 0x80388cd0[ch]  (accessor getDevType 0x80053424(ch); init value 253; 0x13 = TaTaCon, 2 = classic, 1 = nunchuk)
    8006dec4 bl 0x8006e448(&Remocon  0x8038136c, ch)
    8006ded0 bl 0x8006e448(&Classic  0x80381300, ch)
    8006dedc bl 0x8006e448(&Drum     0x803813d8, ch)      (FreeStyle/Nunchuk object 0x80381444 is NEVER updated -> nunchuk is dead)
Sample (0x42 B, CONFIRMED from readers): +0 core hold u16, +0x28 ext type u8, +0x29 err s8 (0 ok), +0x2a ext buttons u16, +0x40 data format u8.
Count = number of samples this frame (newest first at index 0).

## 2. Mapping drum hits (CONFIRMED)
Pad objects (size 0x6c each) at 0x80381300: Classic +0x000, Remocon +0x06c(0x8038136c), Drum(TaTaCon) +0x0d8(0x803813d8), FreeStyle(Nunchuk) +0x144(0x80381444).
Layout: hold[ch] +0x00, trig +0x10, release +0x20, repeat +0x30, rep counters +0x40/+0x50, flag bytes +0x60, mask +0x64, classinfo ptr +0x68.
Masks (set at 0x8006dd94..): Remocon 0xF (dpad, via filter), Classic 0xC003 (dpad), Drum 0, FreeStyle 0.
Classinfo (+0x68): +8 = dpad filter(this,ch,newbits&mask,oldbits&mask) (Remocon 0x8006ea7c, Classic 0x8006e584, Drum 0x8006e6e0 identity), +12 = readRaw(this,ch):
  - Remocon 0x8006eb14: OR of sample+0 (u16) over all samples with err 0 or -7. Ends `mr r3,r28` @0x8006ebd8. If count==0 -> OLD hold reused (this[ch]).
  - Classic 0x8006e624: OR sample+0x2a where ext type(+0x28)==2, err==0, fmt(+0x40)==7. count==0 -> old hold reused.
  - Drum    0x8006e6e8: OR sample+0x2a where ext type==0x13, err==0, fmt==0x11 (WPADTko TaTaCon). count==0 -> old hold reused.
  - FreeStyle 0x8006e7ac: nunchuk (KPAD sample dev==1,fmt 4): hold&0x6000 (Z/C) + stick thresholds -> bits 1,2,4,8. NOT updated per frame => unused.
Generic per-object update 0x8006e448(this, ch) (non-leaf):
    raw=readRaw()&0xffff; old=this[ch]; new=(raw&~mask)|filter(raw&mask,old&mask); this[ch]=new; trig=(old^new)&new; rel=(old^new)&old; repeat logic.
Mapper IsPressed(kind r3 {0 hold,1 trig,2 release,3 repeat}, ch r4, action r5, devflags r6) = 0x8006ebfc.
  Wrappers: 0x80053578 (trig; args ch,action,flags) , 0x8005e5ac (kind 3 repeat), 0x80053590 tail-call.
  devflags: bit0 (1) Remocon: always evaluated; bit1 (2) Classic: only if getDevType(ch)==2; bit2 (4) Nunchuk: devtype==1 (dead hold);
            bit3 (8) TaTaCon: only if getDevType(ch)==0x13; bit4 (0x10) "dev16": ch 0/1 only, tag table 0x8038a1d0 (unused).
  ALL game callers (drum faces and menus) pass devflags=11 (core|classic|tatacon).
  Per-channel style table at 0x8038a210 + ch*20: [0]=Remocon style [4]=Classic [8]=Nunchuk [12]=TaTaCon [16]=dev16; set by setStyle(ch,s0,s1,s2,s3,s4) = 0x8006f014.
  Action tables: base 0x80226650, row = 7 words (action 0..6), 0x1c bytes per style:
    Remocon 0x80226650 (6 styles) | Classic 0x802266f8 (6) | Nunchuk 0x802267a0 (3) | TaTaCon 0x802267f8 (4) | dev16 0x80226868 (4)
  Gameplay drum style setter at 0x8005346c (called from 0x80053324): setStyle(ch, byte0(opt), byte1(opt), 0, 0, 0) with opt=0x80090764(0x8008d098(...));
     then hit mask = IsTrig(ch, action 0..3, 11) for 4 actions (0x800534dc/f0/504/518). => Remocon style = option byte0, Classic style = option byte1,
     TaTaCon ALWAYS style 0, Nunchuk not supported.
  Menu style set (e.g. 0x80056b54, 0x8005ec24, 0x800bb9e0): (Remocon 2, Classic 3, nun 1, tata 1, dev 1). Song-select style (0x800bc134): (4,4,1,2,1).
  Actions 0..3 = don-L, ka-L, don-R, ka-R. Menu actions: 0 left,1 right,2 decide,4 start,5 home,6 cancel.
  Bit values:
    Remocon (Wiimote hold): LEFT1 RIGHT2 DOWN4 UP8 PLUS10 TWO100 ONE200 B400 A800 MINUS1000 HOME8000
      style0 (sideways): a0=LEFT|DOWN(5) a1=ONE(200) a2=RIGHT|UP(a) a3=TWO(100) a4=PLUS a5=HOME ; style1: 9,100,6,200
      style2 (menu): a0=9 a1=6 a2=A|TWO(900) a4=PLUS a5=HOME a6=ONE ; style3: 8,4,1,2,A(800),-,B(400) ; style4: 8,4,900,0,PLUS,HOME,2
    Classic (CL bits): UP1 LEFT2 ZR4 X8 A10 Y20 B40 ZL80 R200 PLUS400 HOME800 MINUS1000 L2000 DOWN4000 RIGHT8000
      style0: a0=c003 (dpad) a1=0078 (X|A|Y|B) a2=2080 (L|ZL) a3=0204 (R|ZR) ; style1: c000,0060,0003,0018 ; style2: 4002,0050,8001,0028 ;
      style3 (menu): 0002,8000,0010(A),-,PLUS,HOME,B(40)... a4=0400 a5=0800 ; style4: 0002,8000,0010,0,0400,0800,0001
    TaTaCon: style0 a0..a3 = 0x40 (center L), 0x10 (rim L), 0x20 (center R), 0x08 (rim R); style1/2 (menu): left=0x20 right=0x08 decide=0x50.
  CLASSIC IS NATIVELY SUPPORTED IN GAMEPLAY (flag 2 included, style = per-player option byte1), mapping above (style 0: dpad=don-L, face=ka-L, L/ZL=don-R, R/ZR=ka-R). Nunchuk: NOT supported.
  Other raw users: Remocon trig/rep getters (0x8006e1dc 94 callers, 0x8006e234 100 callers, 0x8006e1b0 hold, 0x8006e208 release) are called directly with
  Wiimote masks e.g. boot screens (0x800335fc..: ch0 rep &5/&0xA, trig &0x900 decide, &0x600 cancel). These only see the Remocon object.
4 players: everything is per-channel 0..3 (poll loops 4 ch; menus loop ch < playercount from 0x800367c4(0x80033e9c())); style table per ch.

## 3. Hold-word injection (design differs from game 1)
No single leaf "core hold maker". Each pad class has readRaw, and all share ONE non-leaf update 0x8006e448. BEST HOOK:
    0x8006e470: 4e800421 bctrl            (calls this->classinfo->readRaw)
    0x8006e474: 547e043e clrlwi r30,r3,16  <- REPLACE with `bl hook`; r3 = raw hold from readRaw
  At that point: r27 = this (object ptr), r28 = ch. r3-r12 are dead (r3 is the input), r29/r30/r31 are rewritten right after (and saved by prologue
  0x80113bec), so hook may clobber r0,r3-r12,r29-r31; MUST preserve r27,r28,r1; LR is already saved (non-leaf, bctrl follows) so bl is safe.
  Hook must return r30 = (raw_with_injection) & 0xFFFF (it replaces the clrlwi). Stuck-bit hazard: when count==0 (0x80388cc0[ch] <= 0, always true for a GC-only
  channel) readRaw returns the OLD merged hold, so hook must do raw = (count>0 ? raw : 0) | gcbits for the injected objects.
  Hook logic: if this==0x803813d8 (Drum): raw |= GC->{0x40,0x10,0x20,0x08}[ch]   (all 4 faces, style 0 fixed - independent of options)
              if this==0x8038136c (Remocon): raw |= GC menu bits (A->0x800, B->0x400, START->0x10) (A/B/PLUS are not used by drum styles 0/1; avoid injecting
              dpad/ONE/TWO here: they are drum faces in remocon style 0/1). dpad navigation: put D-pad L/R into the Drum bits (menu tata style = L 0x20, R 0x08, decide 0x50).
  Alternative per-object sites (final value just before return): Remocon `mr r3,r28` 0x8006ebd8 (7f83e378), Classic `mr r3,r30` 0x8006e6bc (7fc3f378), Drum `mr r3,r30` 0x8006e780 (7fc3f378).
  (Those readRaw functions are non-leaf and share prologue/epilogue; the update hook is simpler.)
  Remocon dpad bits pass the diagonal filter 0x8006ea7c (only single direction kept); injected before the filter.

## 4. Connected / spoof
- "Connected" for a player = probe ret 0x80388ce0[ch]==0 (used by pause/disconnect check 0x80089de4: ret==-1 => disconnected; script getPadProbe 0x800c00b0 = (ret != -1);
  getPadType 0x800c010c requires ret==0 then maps getDevType). getDevType(ch) = 0x80388cd0[ch] (init 253). Gameplay Tata path needs getDevType==0x13 only (not the probe).
- PATCH SITE: `bl WPADProbe` @0x8006de98 (48138169): replace with `bl wrapper(ch r3, &type r4)`; wrapper calls 0x801a6000; if ret!=0 and a GC pad/bongo is present on port ch:
  *type=0x13, return 0. (Real Wiimote players untouched.) The poll then stores ret/type itself at 0x8006dea4/0x8006deb8. This makes the game treat the GC player as
  a connected TaTaCon (drum style 0 for gameplay, menu tata style) - GC pad also gets probe ok for the disconnect checks.
- Per-frame GC sampling: wrapper at `bl 0x8006dde8` @0x800950e0 (4bfd8d09): read SI once per frame, store gc16[4], then call 0x8006dde8.
  (Alternatively sample inside the probe wrapper.)
- PADInit 0x80194580 is already called; SI polling for the connected pad is enabled by the PAD lib's callbacks (GUESS: verify in Dolphin).

## 5. Free space (CONFIRMED by DOL header and code scan)
DOL sections: text0 0x80004000(0x2740) text1 0x8002f8c0(0x1e4440); data7 0x80006740 data8 0x8001d680 data9 0x80213d00 data10 0x80213dc0 data11 0x80213e00
data12 0x80220ea0 data13 0x8036cae0 data14 0x80370180; BSS 0x8036f2e0 size 0xaa9b0 (ends 0x80419c90; arena starts after it -> don't append data there).
=> text slots 2..6 and data slots 15,16,17 are free. Low mem 0x80001800..0x80003000: no code reference (scan of lis 0x8000 + offset) -> free.
(0x80003000-0x80003100 / 0x800030xx are OS globals, used.)
