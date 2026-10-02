# Taiko no Tatsujin Wii 2 (JP) -- game 3 (S2TJAF) input findings  [taiko3.dol, ghydra port 8203]

Tools: dol.py/dis.py/fstarts.py/xr.py plus new blx.py (bl xrefs) and d13.py (r13-relative xrefs) in the taiko dir.
Status tags: CONFIRMED = traced in code, GUESS = inferred.

## 0. Layout / SDK (CONFIRMED)
- DOL: text0 0x80004000 (0x26a0, .init), text1 0x800322a0 (0x1d21e0); data 7..14 used (0x800066a0, 0x80020700, 0x80204480,
  0x80204500, 0x80204520, 0x80238220, 0x8080adc0, 0x8080e220); BSS field 0x80398880 +0x476ebc (=0x8080f73c).
- r1=0x8081f740  r2=0x80816220  r13=0x80812dc0  (set at 0x8000421c..0x80004230).
- SDK funcs: KPADInit 0x80185694, KPADRead 0x80184d7c (ch, buf, 16) -> count, WPAD-ring reader/copy 0x8018646c (ch, buf, n)
  (copies 56-byte samples, ring at 0x807f0f00+ch*0x570), WPADProbe 0x801abbfc (ch, &type) 0 ok/-1 none,
  PADInit 0x8019ae18, OSDisableInterrupts 0x801930dc / Restore 0x80193104, memcpy 0x80004338, memset 0x80004688.
- KPAD button injection (gbatemp 'andi. r0,rX,0x9FFF'): 0x80182488 = `70c99fff andi. r9,r6,0x9fff` (rA=r9 as predicted); this is the
  function ENTRY (previous word 0x80182484 is blr). args: r3=kpad ch struct, r4=dev type/format, r6=core btn, r8=ext btn.
  Differences vs game 1: also accepts r4==1 (nunchuk: merges Z/C 0x6000 into core word) and r4 in {2,0x10,0x11,0x13}.
- Libs in this DOL are the Mar 10 2009 build (0x4199_60831) vs game 1's Sep 2008 (60726).

## 1. Per-frame poll (CONFIRMED)
- Function 0x8005fe6c (prologue stwu r1,-32; non-leaf). Called from the main loop at 0x80111948 (`4bf4e525 bl 0x8005fe6c`,
  loop = 0x80111948..0x80111978, function 0x80111938 saves LR) -> a `bl` there can be redirected to a wrapper (wrapper calls the original then does GC/bongo work).
- Body for ch 0..3 (r30=ch, r31=0x803e5400):
    0x8005fe94 OSDisableInterrupts
    0x8005feb0 bl KPADRead(ch, 0x803e55c0+ch*0xB00, 16) -> count -> stored 0x803e81c0[ch]           (words 48124ecd 7c651b78 57c0103a 389f2dc0 7c64012e)
    0x8005fed4 bl 0x8018646c(ch, 0x803e8260+ch*0x230)  copies <=10 x 0x38 samples   (word 48126599)
    0x8005fedc OSRestoreInterrupts
    0x8005fee0 type=253 -> [r1+8];  0x8005fef0 bl WPADProbe(ch,r1+8)   (word 4814bd0d)
        ret -> 0x803e81e0[ch]  ; if ret==0: type -> 0x803e81d0[ch]  (stale type kept otherwise; init value 253)
    0x8005ff1c/28/34: bl 0x8006049c(obj,ch) for obj = 0x803e546c (Remocon), 0x803e5400 (Classic), 0x803e54d8 (TaTaCon); the nunchuk obj 0x803e5544 is NOT updated here.
- Sample (0x38 B) layout identical to game 1: +0 core btn u16, +0x28 ext type u8, +0x29 status s8, +0x2a ext btn u16, +0x36 data fmt.
  Getters: 0x8005ff60(ch)=count, 0x8005ff90(ch)=sample buf, 0x8005ff74(ch,idx)= KPADStatus (0xB0 each) at 0x803e55c0+ch*0xB00,
  0x8004b924(ch)=dev type table 0x803e81d0[ch], 0x800eac58(ch)=probe ret table 0x803e81e0[ch].
- Pad objects (static ctor 0x800602b4; base ctor sets vt 0x8023e9c0 'IO::CPadCommon'; vtable +8 = filter fn, +0xc = hold maker; +0x64 mask word; +0x68 vtable ptr):
    0x803e5400 IO::CPadClassic  (vt 0x8023e9e0; hold maker 0x80060678; mask 0xC003)
    0x803e546c IO::CPadRemocon  (vt 0x8023ea70; hold maker 0x80060b68; filter 0x80060ad0; mask 0x000F)
    0x803e54d8 IO::CPadDrum     (vt 0x8023ea10; hold maker 0x8006073c; mask 0)
    0x803e5544 IO::CPadFreeStyle (nunchuk; vt 0x8023ea40; hold maker 0x80060800; mask 0)
  each obj: +0 hold[4] +0x10 trig[4] +0x20 rel[4] +0x30 rep[4].  Generic update 0x8006049c(obj,ch):
    new = vt[3](obj,ch); old=obj[ch]; obj[ch] = (new & ~mask) | vt[2](obj,ch,new&mask,old&mask); trig=(old^h)&h; rel=(old^h)&old.
  (0x800604f8 `4e800421 bctrl`, 0x800604fc.. as above). vt[2] for Remocon (0x80060ad0): for the 4 dpad bits only single directions 1/2/4/8 pass straight;
  diagonals pass only if they appeared together from 'old==0' (latch byte at obj+ch+0x60), otherwise old single direction is kept. Bits above 0xF are untouched.
- Safe in-poll redirect sites (all non-leaf): 0x8005fed4, 0x8005fef0 (probe), 0x8005feb0. Best generic per-frame hook: 0x80111948.

## 2. IsPressed mapper and action tables (CONFIRMED)
- Mapper: 0x80060c50 `IsPressed(kind r3, ch r4, action r5, devflags r6)`; kind 0 hold,1 trig,2 rel,3 rep. 3 tail-call wrappers (all `b 0x80060c50`):
    0x80039858 -> kind 1 (trig)   [b at 0x80039870]
    0x8004fc44 -> kind 3 (rep)    [b at 0x8004fc5c]
    0x800a4f78 -> kind 0 (hold)   [b at 0x800a4f90]    (wrapper = mr r7,r3; mr r0,r4; mr r6,r5; li r3,K; mr r4,r7; mr r5,r0; b)
  EVERY caller passes devflags = 11 (li r5,11): bit0 core remote | bit1 classic | bit3 TaTaCon. (bit2 = nunchuk and bit4 'dev4' never passed.)
  Verified by scanning all 1+... callers (trig actions 0,1,2,3,4,6; rep 0,1; hold 0,1), all with r5=11.
- Structure: bit0 -> Remocon obj getter (0x80060204 hold /0x80060230 trig /0x8006025c rel /0x80060288 rep) & row core[style]
  bit1 -> only if devtype(0x8004b924(ch))==2: Classic obj (0x8005fff4/0x80060020/0x8006004c/0x80060078) & row classic[style]
  bit2 -> devtype==1 (nunchuk) 0x80060154..; bit3 -> devtype==0x13 (19): Drum obj (0x800600a4/d0/fc/128) & row tatacon[style]
  bit4 -> dev4 stub. (Some menu code reads the Remocon obj directly: 0x80060230 callers 0x80058a98,0x80112884..; 0x80060288 callers 0x80035930..; so the Remocon hold hook also feeds those.)
- Per-channel style selector (BSS) 0x803e8f50 + ch*20: [0]=core style [1]=classic [2]=nunchuk [3]=tatacon [4]=dev4. Setter 0x80061068(ch,core,classic,nunchuk,tatacon,dev4).
  Menus call it with (2,3,1,1,1)  (e.g. 0x800396a4, 0x8004ca30, 0x8004d880, 0x8004fa80 ...).
  Gameplay (0x8004b664 per-player input gather, 0x8003f18c, 0x801077d8): core style = byte3 of config word (struct+5436, getter 0x8010cc34), classic style = byte2 (0x8010cc68),
  nunchuk=tatacon=dev4=0.  Config word is set from the options menu by 0x800e9e90 (core) / 0x800e9d48 (classic) (Lua setControllerRemocon @0x800efa98, setControllerClassic @0x800efae0).
  Default value / allowed range not traced: GUESS style 0 default, 0..2 selectable.
- Action tables, r31 = 0x8023eaa0, row = 7 words (actions 0..6), 0x1c per style (same layout as game 1, different contents/row counts):
    core    @0x8023eaa0 (style0..3 + zero row4): bits Wii btn (LEFT1 RIGHT2 DOWN4 UP8 PLUS10 TWO100 ONE200 B400 A800 MINUS1000 HOME8000)
       s0: 5,200,A,100,10,8000,0   (don-L=LEFT|DOWN, ka-L=ONE, don-R=RIGHT|UP, ka-R=TWO)
       s1: 9,100,6,200,10,8000,0   (LEFT|UP, TWO, RIGHT|DOWN, ONE)
       s2: 9,6,900,0,10,8000,200   (MENU: left,right,decide=A|TWO,-,start=PLUS,home,cancel=ONE)
       s3: 8,4,1,2,800,0,400       (menu up,down,left,right,A,-,B)
    classic @0x8023eb2c: bits CL (UP1 LEFT2 ZR4 X8 A10 Y20 B40 ZL80 R200 PLUS400 HOME800 MINUS1000 L2000 DOWN4000 RIGHT8000)
       s0: C003,78,2080,204,400,800,0   (don-L=dpad, ka-L=face X|A|Y|B, don-R=L|ZL, ka-R=R|ZR)
       s1: C000,60,3,18,400,800,0       (RIGHT|DOWN, Y|B, UP|LEFT, X|A)
       s2: 4002,50,8001,28,400,800,0    (DOWN|LEFT, A|B, RIGHT|UP, X|Y)   <- mirrors core s0
       s3: 2,8000,10,0,400,800,40       (MENU: left,right,decide=A,-,start=PLUS,home,cancel=B)
    nunchuk @0x8023ebb8: s0: 3,C,2000,4000,0,0,0 ; s1: 1,2,2000,0,0,0,4000   (stick bits / Z / C; unused by callers)
    tatacon @0x8023ec0c: s0: 40,10,20,8,0,0,0 (CENTER_L, RIM_L, CENTER_R, RIM_R) ; s1: 20,8,50,0,0,0,0
    dev4    @0x8023ec60: s0: A00,500,10,10 ; s1: A00,500,1000,0   (unused)
- Gameplay semantic (0x8004b664 .. 0x8004b8ec): actions 0..3 -> 4 booleans; result word (obj+0x14): bit0 = act0|act1, bit1 = act0&act1 seen within 3-frame history,
  bit2 = act2|act3, bit3 = act2&act3 within 3 frames. So pair (0,1) = left side (don-L, ka-L) and pair (2,3) = right side (don-R, ka-R); matches TaTaCon CENTER_L/RIM_L/CENTER_R/RIM_R. (pair roles CONFIRMED, which of a pair is don vs ka = GUESS from TaTaCon row.)
  Classic -> drum faces for gameplay: per classic style row above (style 0: dpad/face/L-ZL/R-ZR). Used only if WPADProbe dev type == 2 and fmt==7 samples.

## 3. Core remote final hold (CONFIRMED)
- Hold maker = Remocon vt[3] = 0x80060b68 (non-leaf: stwu r1,-32, stw lr 36(r1), saves r28-r31).
  Registers at the end: r28 = final 16-bit hold, r29 = sample count, r30 = obj 0x803e546c, r31 = ch. r3 is the (free) sample ptr.
  0x80060c18: 2c1d0000 cmpwi r29,0 ; 40820010 bne 0x80060c2c ; 57e0103a slwi r0,r31,2 ; 7c1e002e lwzx r0,r30,r0 ; 541c043e clrlwi r28,r0,16 (old hold re-used when count==0) ;
  **0x80060c2c: 7f83e378 mr r3,r28** <- hook (return value in r3); followed by 83e1001c lwz r31,28(r1)...
  Hook plan: replace 0x80060c2c with `bl wrapper` (LR already saved at 36(r1) so clobbering LR is safe). wrapper: in r28=hold r29=count r30=obj r31=ch; return new hold in r3.
  Free regs: r0, r3-r12, cr0-cr1(crf), ctr (everything volatile); r28-r31 live-in but may be read; must preserve r1,r28-r31.
  Accumulation: ORs lhz@sample+0 of every sample with status (+0x29) == 0 or -7 (it first marks -7 on a good sample following a bad one).
  After return the generic update masks bits 0xF through the dpad filter (diagonal caveat above). ONE/TWO/A/B/PLUS/HOME are not filtered.
- Same-pattern exits: Classic 0x80060710 `7fc3f378 mr r3,r30` (r30 hold,r29 ch,r31 count,r28 obj) ; TaTaCon 0x800607d4 (bytes at 0x800607c8.. 57a0103a 7c1c002e 541e043e 7fc3f378).

## 4. PADInit / WPADProbe / connected gating
- PADInit 0x8019ae18: game DOES call it (CONFIRMED): 0x8005fce0 (in pad init 0x8005fcac, word 4813b139) and 0x80110c0c (word 4808a20d). No game code calls any other PAD-lib function
  (only SDK-internal callers), so GC pads are initialised/SI-polled but never read by the game (CONFIRMED by bl scan; PADRead address not identified).
- WPADProbe 0x801abbfc. Game call sites: 0x8005fef0 (poll), 0x8010a254 (pointer/cursor update, result: <-1.. -4 => skip, 0/-7 ok).
- Connected decision (CONFIRMED path, GUESS for scripts): player i is 'connected' iff probe table 0x803e81e0[i]==0.
  * Lua getPadProbe @0x800eb9cc (str 0x8026ce64 ref 0x800ef3b4) pushes (0x800eac58(ch)==0) via cntlzw at 0x800eba18.
  * 0x800f2814 same for another binding; 0x800eab5c / 0x800f1974 use probe!=0 -> -1 and map dev type (0x8004b924: 0->1, 1->1, 2->3, 19->2, 251->1, 253->0) for UI icon.
  * 0x801088f8/0x8010898c: pause-on-disconnect: for an active player, probe == -1 -> bit set in obj+0x24 (controller disconnected screen).
  * players-in-session count = singleton(0x80035794)->(0x80036814)=+8.
  Candidate spoof sites: (a) 0x8005fef0 `bl WPADProbe` -> wrapper that calls it then forces r3=0 and *(r4)=type (r4 = &type = r1+8 of caller) when a GC/bongo pad is on that ch;
  stores happen right after (0x8005fef4.. `57c5103a 389f2de0 7c64292e`), type only if r3==0.  (b) or leaf getters: 0x800eac58 (words 5460103a 3c60803f 386381e0 7c63002e 4e800020) -> `b wrapper` returning 0, and 0x8004b924 (… 386381d0 …) for type.
  (a) is preferred: fixes both readers; 0x8010a254 still sees real WPADProbe (harmless).
  With count==0 the Remocon hold maker keeps the old hold, so injecting at 0x80060c2c works without any Wii Remote.

## 5. WPADTko (CONFIRMED string / GUESS role)
- String '<< RVL_SDK - WPADTko  release build: Mar 10 2009 17:18:35' at 0x80392318 (pointer slot 0x8080d260, loaded by tiny fn 0x801bbb24 -> OSRegisterVersion 0x8018d358).
  It exists only in games 2-5 (absent in game 1). It is part of the same Mar-2009 WPAD build (WPAD 17:17:20, KPAD 17:16:54): WPAD lib spans ~0x801aa700-0x801b9100 and has many
  ext-type 0x13/0x11 branches (27 sites vs 2 in game 1's WPAD), i.e. native TaTaCon support in WPAD; the KPAD copy at 0x80182xxx also handles types 0x10/0x11/0x13.
- Game-side TaTaCon data path is UNCHANGED vs game 1: sample +0x28==0x13, +0x29==0 (status ok), +0x36==0x11, buttons u16 @+0x2a (0x8006073c). Classic: +0x28==2, fmt +0x36==7, @+0x2a (0x80060678).
  TaTaCon bit masks (tatacon rows): CENTER_L 0x40, RIM_L 0x10, CENTER_R 0x20, RIM_R 0x08 (same as game 1).
  New in game 3: nunchuk object (type 1) read from KPADStatus (type byte +0x5c==1, err +0x5d==0, fmt +0x5f==4, stick floats +0x60) and KPAD merges Z/C (0x6000) into the core button word (0x80182488 path r4==1);
  nunchuk is not reachable from gameplay because devflags never include 4.

## 6. Free space (CONFIRMED statically)
- DOL uses text slots 0,1 and data slots 7..14 -> text slots 2..6 and data slots 15,16,17 free (header offsets/addrs/sizes are 0).
- Low memory: no code reference (lis 0x8000 + disp scan, r13/r2 are 0x8081xxxx) to 0x80001820..0x80003000 other than OS-lib refs at >=0x80003000 (0x80003000, 0x80003040, 0x800030xx, 0x80003100+). So 0x80001820-0x80002fff (0x17e0 bytes) is free.
- Caution: the DOL BSS field (0x80398880..0x8080f73c) covers data13/14 and everything above 0x80398880 -> do NOT place new sections there.
