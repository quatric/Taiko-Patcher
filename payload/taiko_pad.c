/*
 * Taiko-Patcher payload: GameCube controller + DK Bongo input for Taiko no Tatsujin Wii.
 *
 * The game never reads the GameCube ports, but it already calls PADInit() so the SI hardware
 * poller is running. We read the SI input registers directly and OR the result into the game's
 * own per-channel "button hold" words:
 *   - the TaTaCon (drum) state  -> drum hits + menu left/right/decide, exactly like the real drum
 *   - the Wii Remote core state -> pause (+) and cancel
 *
 * Everything game specific (hook addresses, bit values) is filled in by the patcher:
 *   - tp_cfg                       : bit values for this game
 *   - tp_exit_hold_tk/_core        : 'b <return>' slots, patched with the address after the hook
 *   - tp_exit_poll                 : 'b <original callee>' slot
 * No libc, no small-data, position fixed at link time (see payload.ld).
 */
#include <stdint.h>

typedef uint32_t u32;
typedef uint16_t u16;
typedef uint8_t u8;

#define SI_BASE 0xCD006400u
static inline u32 si_rd(u32 off) { return *(volatile u32 *)(SI_BASE + off); }

/* INBUFH layout of a polled GC pad (analog mode 3):
 *   31 ERRSTAT 30 ERRLATCH 28 START 27 Y 26 X 25 B 24 A | 23 =1 22 L 21 R 20 Z 19 UP 18 DOWN 17 RIGHT 16 LEFT
 *   15:8 stick X  7:0 stick Y ; INBUFL: 31:24 cstick X, 23:16 cstick Y, 15:8 trigger L, 7:0 trigger R */
#define GC_ERRSTAT  0x80000000u
#define GC_START    0x10000000u
#define GC_Y        0x08000000u
#define GC_X        0x04000000u
#define GC_B        0x02000000u
#define GC_A        0x01000000u
#define GC_ORIGIN   0x00800000u
#define GC_L        0x00400000u
#define GC_R        0x00200000u
#define GC_Z        0x00100000u
#define GC_UP       0x00080000u
#define GC_DOWN     0x00040000u
#define GC_RIGHT    0x00020000u
#define GC_LEFT     0x00010000u

#define TP_MAGIC 0x544B5054u /* 'TKPT' */

/* flags */
#define TPF_STICK   0x1u /* left stick acts as D-pad            */
#define TPF_CLAP    0x2u /* DK Bongo clap = ka                  */
#define TPF_CSTICK  0x4u /* C-stick: left=ka-L right=ka-R, up/down = don L/R */

struct tp_cfg {
    u32 magic;
    u32 tk_cl;       /* TaTaCon center-left  (don L) bit in the game's hold word */
    u32 tk_rl;       /* TaTaCon rim-left     (ka L)                              */
    u32 tk_cr;       /* TaTaCon center-right (don R)                             */
    u32 tk_rr;       /* TaTaCon rim-right    (ka R)                              */
    u32 core_start;  /* Wii Remote bit used for pause/start                      */
    u32 core_cancel; /* Wii Remote bit used for cancel/back                      */
    u32 flags;
    u32 stick_thresh;
    u32 clap_thresh;
    u32 obj_drum; /* games 2-5: address of the CPadDrum    state object */
    u32 obj_core; /* games 2-5: address of the CPadRemocon state object */
};

struct tp_state {
    u32 tk_cur[4];
    u32 tk_prev[4];
    u32 core_cur[4];
    u32 core_prev[4];
    u8 present[4]; /* 1 = a GC pad / bongo answered on this port */
    u8 kind[4];    /* 0 none, 1 pad, 2 bongo                     */
    u8 clap[4];    /* clap currently above threshold              */
    u8 side[4];    /* next ka side for claps                      */
    u32 dbg_sipoll; /* debug mirrors (read through a debugger)    */
    u32 dbg_h[4];
    u32 dbg_l[4];
};

struct tp_cfg tp_cfg __attribute__((used)) = {
    TP_MAGIC, 0x40, 0x20, 0x10, 0x08, 0x10, 0x200, TPF_STICK | TPF_CLAP | TPF_CSTICK, 48, 0x50, 0, 0,
};
struct tp_state tp_state __attribute__((used));

void tp_poll_ch(u32 ch) __attribute__((used));
void tp_poll_ch(u32 ch)
{
    const struct tp_cfg *c = &tp_cfg;
    struct tp_state *s = &tp_state;
    if (ch >= 4)
        return;

    u32 tk = 0, core = 0, present = 0, kind = 0;
    u32 sipoll = si_rd(0x30);
    u32 en = (sipoll >> (7 - ch)) & 1; /* SIPOLL enable bit for this port */
    s->dbg_sipoll = sipoll;
    if (en) {
        u32 h = si_rd(ch * 12 + 4);
        u32 l = si_rd(ch * 12 + 8);
        s->dbg_h[ch] = h;
        s->dbg_l[ch] = l;
        if (!(h & GC_ERRSTAT) && (h & GC_ORIGIN)) {
            present = 1;
            kind = 1;
            /* DK Bongos report no sticks at all (main and C stick are both ~0) */
            if (((h & 0xFCFC) == 0) && (((l >> 16) & 0xFCFC) == 0)) {
                kind = 2;
                if (h & (GC_B | GC_Y))
                    tk |= c->tk_cl;
                if (h & (GC_A | GC_X))
                    tk |= c->tk_cr;
                if (c->flags & TPF_CLAP) {
                    u32 amp = l & 0xFF, a2 = (l >> 8) & 0xFF;
                    if (a2 > amp)
                        amp = a2;
                    if (amp >= c->clap_thresh) {
                        if (!s->clap[ch]) {
                            s->clap[ch] = 1;
                            s->side[ch] ^= 1;
                        }
                        tk |= s->side[ch] ? c->tk_rr : c->tk_rl;
                    } else {
                        s->clap[ch] = 0;
                    }
                }
            } else {
                if (h & (GC_B | GC_Y))
                    tk |= c->tk_cl;
                if (h & (GC_A | GC_X))
                    tk |= c->tk_cr;
                if (h & (GC_L | GC_LEFT))
                    tk |= c->tk_rl;
                if (h & (GC_R | GC_RIGHT))
                    tk |= c->tk_rr;
                if (h & GC_DOWN)
                    tk |= c->tk_cl;
                if (h & GC_UP)
                    tk |= c->tk_cr;
                if (c->flags & TPF_STICK) {
                    int sx = (int)((h >> 8) & 0xFF) - 128;
                    int sy = (int)(h & 0xFF) - 128;
                    int t = (int)c->stick_thresh;
                    if (sx <= -t)
                        tk |= c->tk_rl;
                    if (sx >= t)
                        tk |= c->tk_rr;
                    if (sy <= -t)
                        tk |= c->tk_cl;
                    if (sy >= t)
                        tk |= c->tk_cr;
                }
                if (c->flags & TPF_CSTICK) {
                    int cx = (int)((l >> 24) & 0xFF) - 128;
                    int cy = (int)((l >> 16) & 0xFF) - 128;
                    int t = (int)c->stick_thresh;
                    if (cx <= -t)
                        tk |= c->tk_rl;
                    if (cx >= t)
                        tk |= c->tk_rr;
                    if (cy <= -t)
                        tk |= c->tk_cl;
                    if (cy >= t)
                        tk |= c->tk_cr;
                }
                if (h & GC_Z)
                    core |= c->core_cancel;
            }
            if (h & GC_START)
                core |= c->core_start;
        }
    }
    s->tk_cur[ch] = tk;
    s->core_cur[ch] = core;
    s->present[ch] = (u8)present;
    s->kind[ch] = (u8)kind;
}

/* ---- assembler glue ------------------------------------------------------------------
 * Family A (game 1): the hold makers are leaf functions (LR not saved), so the hooks are reached
 * with `b` and leave with `b`. Live-in: r3 = channel, r6 = sample count, r7 = freshly OR-ed
 * hold word (or the previous hold if there were no samples). Clobbers r5, r8-r11 (dead there).
 */
#define HOLD_HOOK(name, cur, prev, exitlabel)                                                     \
    ".global " name "\n" name ":\n"                                                               \
    "  lis    5, tp_state+" cur "@ha\n"                                                           \
    "  slwi   11, 3, 2\n"                                                                         \
    "  addi   5, 5, tp_state+" cur "@l\n"                                                         \
    "  lwzx   10, 5, 11\n"                                                                        \
    "  lis    8, tp_state+" prev "@ha\n"                                                          \
    "  addi   8, 8, tp_state+" prev "@l\n"                                                        \
    "  lwzx   9, 8, 11\n"                                                                         \
    "  cmpwi  6, 0\n"                                                                             \
    "  bne    1f\n"                                                                               \
    "  andc   7, 7, 9\n"                                                                          \
    "1:\n"                                                                                        \
    "  or     7, 7, 10\n"                                                                         \
    "  stwx   10, 8, 11\n"                                                                        \
    ".global " exitlabel "\n" exitlabel ":\n"                                                     \
    "  nop\n"

__asm__(".section .text.stubs,\"ax\"\n"
        ".align 2\n" HOLD_HOOK("tp_hold_hook_tk", "0", "16", "tp_exit_hold_tk")
        HOLD_HOOK("tp_hold_hook_core", "32", "48", "tp_exit_hold_core")

        /* Family B (games 2-5): replaces `clrlwi r30,r3,16` after the getRaw() virtual call inside
         * CPadCommon::update(this=r27, ch=r28). r3 = raw hold; result must be in r30.
         * The old hold is re-used by the game when there are no samples, so the bits injected
         * last frame are stripped first (tp_state.*_prev) and the new ones OR-ed in. */
        ".global tp_update_hook\n"
        "tp_update_hook:\n"
        "  clrlwi 30, 3, 16\n"
        "  lis    4, tp_cfg@ha\n"
        "  addi   4, 4, tp_cfg@l\n"
        "  lwz    5, 40(4)\n" /* cfg.obj_drum */
        "  cmpw   27, 5\n"
        "  bne    1f\n"
        "  lis    6, tp_state@ha\n"
        "  addi   6, 6, tp_state@l\n"
        "  b      2f\n"
        "1:\n"
        "  lwz    5, 44(4)\n" /* cfg.obj_core */
        "  cmpw   27, 5\n"
        "  bnelr\n"
        "  lis    6, tp_state+32@ha\n"
        "  addi   6, 6, tp_state+32@l\n"
        "2:\n"
        "  slwi   7, 28, 2\n"
        "  lwzx   8, 6, 7\n"  /* cur  */
        "  addi   6, 6, 16\n"
        "  lwzx   9, 6, 7\n"  /* prev */
        "  andc   30, 30, 9\n"
        "  or     30, 30, 8\n"
        "  stwx   8, 6, 7\n"
        "  blr\n"

        /* Replaces `bl WPADProbe` in the per-frame poll (r3 = channel, r4 = &devtype). It polls the
         * GC port for that channel, runs the real probe, and if a GC pad / bongo answered it reports
         * the port as a connected TaTaCon (type 0x13) so the game takes its drum path. */
        ".global tp_probe_wrap\n"
        "tp_probe_wrap:\n"
        "  stwu   1, -32(1)\n"
        "  mflr   0\n"
        "  stw    0, 36(1)\n"
        "  stw    3, 8(1)\n"
        "  stw    4, 12(1)\n"
        "  bl     tp_poll_ch\n"
        "  lwz    3, 8(1)\n"
        "  lwz    4, 12(1)\n"
        ".global tp_call_probe\n"
        "tp_call_probe:\n"
        "  nop\n" /* patched: bl <real WPADProbe> */
        "  lwz    5, 8(1)\n"
        "  lis    6, tp_state@ha\n"
        "  addi   6, 6, tp_state@l\n"
        "  add    6, 6, 5\n"
        "  lbz    7, 64(6)\n" /* present[ch] */
        "  cmpwi  7, 0\n"
        "  beq    3f\n"
        "  li     3, 0\n"
        "  li     0, 0x13\n"
        "  lwz    4, 12(1)\n"
        "  stw    0, 0(4)\n"
        "3:\n"
        "  lwz    0, 36(1)\n"
        "  mtlr   0\n"
        "  addi   1, 1, 32\n"
        "  blr\n");
