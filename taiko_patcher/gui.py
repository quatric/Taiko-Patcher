#!/usr/bin/env python3
"""Drag-and-drop GUI: drop a Taiko no Tatsujin Wii disc image (or main.dol / extracted folder) on the window.

Disc images are replaced in place (USB loaders key off the file's name and folder); the untouched original is
kept alongside as <name>.bak. A bare .dol or an extracted folder is patched the same way (.bak / .orig).
"""
import os
import queue
import shutil
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

if __package__ in (None, ""):
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    __package__ = "taiko_patcher"

from taiko_patcher import __version__
from taiko_patcher.disc import find_wit, kind_of, patch_any
from taiko_patcher.patcher import FLAG_CLAP, FLAG_CSTICK, FLAG_STICK, PatchError

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAVE_DND = True
except ImportError:                                    # fall back to click-to-browse
    HAVE_DND = False

BASE = TkinterDnD.Tk if HAVE_DND else tk.Tk


def asset(name):
    root = getattr(sys, "_MEIPASS", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    return os.path.join(root, "assets", name)


def run_patch(path, log, done, gc=True, classic=True, stick=True, clap=True):
    try:
        if not (gc or classic):
            raise PatchError("nothing selected: tick at least one patch")
        flags = FLAG_CSTICK | (FLAG_STICK if stick else 0) | (FLAG_CLAP if clap else 0)
        kind = kind_of(path)
        if kind == "image":
            if not find_wit():
                raise PatchError("wit (Wiimms ISO Tool) not found: install it from https://wit.wiimm.de/ and put it on PATH")
            staged = os.path.join(os.path.dirname(os.path.abspath(path)), ".taiko-patcher-staged" + os.path.splitext(path)[1])
            try:
                patch_any(path, staged, gc=gc, classic=classic, flags=flags, log=log)
                backup = path + ".bak"
                if os.path.exists(backup):
                    log("backup already exists, keeping it: %s" % os.path.basename(backup))
                else:
                    shutil.copyfile(path, backup)
                    log("backed up original -> %s" % os.path.basename(backup))
                shutil.move(staged, path)
            finally:
                if os.path.exists(staged):
                    os.remove(staged)
            out = path
        elif kind == "dol":
            staged = path + ".new"
            patch_any(path, staged, gc=gc, classic=classic, flags=flags, log=log)
            if not os.path.exists(path + ".bak"):
                shutil.copyfile(path, path + ".bak")
            shutil.move(staged, path)
            out = path
        else:
            out = patch_any(path, None, gc=gc, classic=classic, flags=flags, log=log)
        log("done: patched in place, %s" % os.path.basename(out))
        done(True, out)
    except Exception as e:                              # shown to the user, never swallowed
        log("ERROR: %s" % e)
        done(False, str(e))


class App(BASE):
    def __init__(self):
        super().__init__()
        self.title("Taiko-Patcher %s" % __version__)
        self.geometry("620x520")
        try:
            self.iconphoto(True, tk.PhotoImage(file=asset("icon.png")))
        except Exception:
            pass
        self.msgq = queue.Queue()
        self.busy = False

        try:                                             # the game logo above the drop zone
            img = tk.PhotoImage(file=asset("logo.png"))
            self.logo = img.subsample(max(1, round(img.width() / 190)))
            tk.Label(self, image=self.logo).pack(pady=(10, 0))
        except Exception:
            pass

        hint = ("Drop a .wbfs / .iso here\n(or a main.dol / extracted game folder)\n\n(or click to choose one)"
                if HAVE_DND else "Click to choose a .wbfs or .iso")
        self.drop = tk.Label(self, text=hint, relief="ridge", bd=2, padx=10, pady=24, cursor="hand2")
        self.drop.pack(fill="x", padx=10, pady=10)
        self.drop.bind("<Button-1>", lambda e: self.pick())
        if HAVE_DND:
            self.drop.drop_target_register(DND_FILES)
            self.drop.dnd_bind("<<Drop>>", self.on_drop)

        opts = tk.LabelFrame(self, text="Patches")
        opts.pack(fill="x", padx=10)
        self.gc = tk.BooleanVar(value=True)
        tk.Checkbutton(opts, text="GameCube controller and DK Bongos (ports 1-4)", variable=self.gc).pack(anchor="w")
        self.stick = tk.BooleanVar(value=True)
        tk.Checkbutton(opts, text="    left stick works as D-pad", variable=self.stick).pack(anchor="w")
        self.clap = tk.BooleanVar(value=True)
        tk.Checkbutton(opts, text="    DK Bongo clap = ka", variable=self.clap).pack(anchor="w")
        self.classic = tk.BooleanVar(value=True)
        tk.Checkbutton(opts, text="Classic Controller: ZL / ZR also hit ka (Taiko Wii 1)", variable=self.classic).pack(anchor="w")

        tk.Label(self, text="Supports all five Taiko no Tatsujin Wii games. The original is kept alongside as <name>.bak",
                 fg="#666").pack(pady=(6, 0))
        self.log = tk.Text(self, height=12, state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True, padx=10, pady=10)
        self.after(100, self.poll_queue)

    def on_drop(self, event):
        paths = self.tk.splitlist(event.data)           # handles {braced paths with spaces}
        if paths:
            self.start(paths[0])

    def pick(self):
        if self.busy:
            return
        p = filedialog.askopenfilename(title="Select disc image or main.dol",
                                       filetypes=[("Wii disc image / DOL", "*.wbfs *.iso *.dol"), ("All files", "*")])
        if p:
            self.start(p)

    def append_log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def poll_queue(self):
        try:
            while True:
                kind, payload = self.msgq.get_nowait()
                if kind == "log":
                    self.append_log(payload)
                else:
                    ok, msg = payload
                    self.busy = False
                    self.drop.configure(state="normal")
                    (messagebox.showinfo if ok else messagebox.showerror)("Done" if ok else "Patch failed",
                                                                           "Patched in place:\n%s" % msg if ok else msg)
        except queue.Empty:
            pass
        self.after(100, self.poll_queue)

    def start(self, path):
        if self.busy:
            return
        if kind_of(path) == "unknown":
            messagebox.showerror("Unsupported", "%s is not a disc image, main.dol or extracted game folder." % path)
            return
        self.busy = True
        self.drop.configure(state="disabled")
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        threading.Thread(target=run_patch, daemon=True, args=(
            path, lambda t: self.msgq.put(("log", t)), lambda ok, m: self.msgq.put(("done", (ok, m))),
            self.gc.get(), self.classic.get(), self.stick.get(), self.clap.get())).start()


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
