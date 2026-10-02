"""Per-game profiles. Every address was traced in the game's main.dol (see docs/ for the notes).

The generic payload (payload/taiko_pad.c) hooks the games in one of two ways:

family "A" (game 1):  the TaTaCon / Wii Remote button-state makers are leaf functions, so two
                      `b` hooks inject into their final 16-bit hold word (r7 at `hold_*`).
family "B" (games 2-5): all pad classes share CPadCommon::update(this, ch); one `bl` hook
                      replaces `clrlwi r30,r3,16` after the getRaw() virtual call and tells the
                      classes apart by object address (`obj_drum`, `obj_core`).

Both families also wrap the per-channel `bl WPADProbe` in the per-frame poll (`probe_call`): that is
where the GC port is polled and where a GC pad / DK Bongo is reported as a connected TaTaCon.
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Site:
    addr: int
    expect: int  # original instruction word (sanity check before patching)


@dataclass
class TablePatch:
    addr: int
    expect: int
    new: int
    what: str


@dataclass
class Game:
    key: str
    title: str
    id6: str
    dol_sha1: Optional[str] = None
    family: str = ""
    note: str = ""
    probe_call: Optional[Site] = None
    # family A
    hold_tk: Optional[Site] = None
    hold_core: Optional[Site] = None
    # family B
    update_hook: Optional[Site] = None
    obj_drum: int = 0
    obj_core: int = 0
    cfg: dict = field(default_factory=dict)
    tables: list = field(default_factory=list)

    @property
    def supported(self) -> bool:
        return bool(self.family)


SLWI_R11_R3_2 = 0x546B103A  # slwi r11,r3,2
CLRLWI_R30_R3_16 = 0x547E043E  # clrlwi r30,r3,16

# TaTaCon button bits in the game's 16-bit hold word (identical in all five games):
#   center-left 0x40 (don L)  rim-left 0x20 (ka L)  center-right 0x10 (don R)  rim-right 0x08 (ka R)
TK = dict(tk_cl=0x40, tk_rl=0x20, tk_cr=0x10, tk_rr=0x08, core_start=0x10, core_cancel=0x200)

GAMES = {
    "taiko1": Game(
        key="taiko1", title="Taiko no Tatsujin Wii", id6="R2JJAF",
        dol_sha1="e35331bd0820bd368bd067fbef6b01b2de94c98e", family="A",
        probe_call=Site(0x80033EC0, 0x480EF93D),
        hold_tk=Site(0x800A4FBC, SLWI_R11_R3_2),
        hold_core=Site(0x800C7520, SLWI_R11_R3_2),
        cfg=dict(TK),
        tables=[
            # Classic Controller style 0 (gameplay): add ZL to ka-L (L) and ZR to ka-R (R)
            TablePatch(0x80211F9C, 0x00002000, 0x00002080, "Classic style0 ka-L: L -> L|ZL"),
            TablePatch(0x80211FA0, 0x00000200, 0x00000204, "Classic style0 ka-R: R -> R|ZR"),
        ],
    ),
    "taiko2": Game(
        key="taiko2", title="Taiko no Tatsujin Wii: Chou Goukaban", id6="S5KJAF", family="B",
        dol_sha1="56abfbb76f0ff3ecdb03cbbe7390124a7a724ab5",
        probe_call=Site(0x80096228, 0x481839D9),
        update_hook=Site(0x80096804, CLRLWI_R30_R3_16),
        obj_drum=0x804168B8, obj_core=0x8041684C, cfg=dict(TK),
    ),
    "taiko3": Game(
        key="taiko3", title="Taiko no Tatsujin Wii: Dodoon to 2-daime!", id6="S2TJAF", family="B",
        dol_sha1="b269a6fa55031c8d2f6e329491ea8b5231d3341b",
        probe_call=Site(0x8005FEF0, 0x4814BD0D),
        update_hook=Site(0x800604C8, CLRLWI_R30_R3_16),
        obj_drum=0x803E54D8, obj_core=0x803E546C, cfg=dict(TK),
    ),
    "taiko4": Game(
        key="taiko4", title="Taiko no Tatsujin Wii: Ketteiban", id6="STJJAF", family="B",
        dol_sha1="640c0ad7123f7c5e72001352a24944fa6976fe41",
        probe_call=Site(0x8007C834, 0x4815ABED),
        update_hook=Site(0x8007CE10, CLRLWI_R30_R3_16),
        obj_drum=0x803D8DF8, obj_core=0x803D8D8C, cfg=dict(TK),
    ),
    "taiko5": Game(
        key="taiko5", title="Taiko no Tatsujin Wii: Minna de Party 3-daime!", id6="S3TJAF", family="B",
        dol_sha1="bffc50c1f25bf187b9e18fb4f2769169bd75de7a",
        probe_call=Site(0x8006DE98, 0x48138169),
        update_hook=Site(0x8006E474, CLRLWI_R30_R3_16),
        obj_drum=0x803813D8, obj_core=0x8038136C, cfg=dict(TK),
    ),
}

BY_ID6 = {g.id6: g for g in GAMES.values()}
