"""InstallTrace desktop UI — dark observability console.

Dependency-free Tkinter UI. Worker threads never call Tk directly.
"""
from __future__ import annotations

import json
import os
import queue
import threading
import tkinter as tk
from collections import Counter
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import core
from .collect import Cancelled, capture, default_roots
from .demo import samples

# Midnight Console palette
BG = "#070B12"
SURFACE = "#0D1420"
SURFACE_2 = "#111B29"
SURFACE_3 = "#162334"
BORDER = "#223247"
BORDER_SOFT = "#182536"
TEXT = "#EAF2FA"
MUTED = "#8292A6"
MUTED_2 = "#627287"
ACCENT = "#5EECC8"
ACCENT_HOVER = "#7CF3D4"
ACCENT_DARK = "#083E35"
BLUE = "#69A7FF"
BLUE_DARK = "#102A4C"
AMBER = "#F4C56A"
AMBER_DARK = "#3D2D10"
RED = "#FF7B84"
RED_DARK = "#431B22"
PURPLE = "#B79CFF"
PURPLE_DARK = "#2B2249"
SUCCESS = "#64E6A8"

FONT_UI = "Segoe UI"
FONT_MONO = "Cascadia Mono"


def _button(parent, text, command, *, primary=False, danger=False, compact=False, width=None):
    """Create a flat modern button with consistent hover states."""
    if primary:
        bg, hover, fg = ACCENT, ACCENT_HOVER, BG
    elif danger:
        bg, hover, fg = RED_DARK, "#5A242D", "#FFB3B8"
    else:
        bg, hover, fg = SURFACE_3, "#1C2D42", TEXT

    kwargs = {
        "text": text,
        "command": command,
        "font": (FONT_UI, 9 if compact else 10, "bold"),
        "bg": bg,
        "fg": fg,
        "activebackground": hover,
        "activeforeground": fg,
        "relief": "flat",
        "bd": 0,
        "highlightthickness": 1,
        "highlightbackground": bg if primary else BORDER,
        "highlightcolor": bg if primary else BORDER,
        "cursor": "hand2",
        "padx": 11 if compact else 16,
        "pady": 6 if compact else 9,
    }
    if width is not None:
        kwargs["width"] = width
    btn = tk.Button(parent, **kwargs)

    def enter(_):
        btn.configure(bg=hover, highlightbackground=hover if primary else BORDER)

    def leave(_):
        btn.configure(bg=bg, highlightbackground=bg if primary else BORDER)

    btn.bind("<Enter>", enter)
    btn.bind("<Leave>", leave)
    return btn


def _chip(parent, text, *, fg=ACCENT, bg=ACCENT_DARK):
    return tk.Label(
        parent,
        text=text,
        font=(FONT_UI, 8, "bold"),
        fg=fg,
        bg=bg,
        padx=8,
        pady=3,
    )


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("InstallTrace 0.2 — installation observability")
        self.geometry("1280x860")
        self.minsize(1020, 700)
        self.configure(bg=BG)

        self.snapshots = {}
        self.result = None
        self.rows = []
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.busy = False

        self._configure_styles()
        self._build_shell()
        self.after(100, self.poll)
        self.protocol("WM_DELETE_WINDOW", self.close)

    # ---------- visual shell ----------
    def _configure_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", background=BG, foreground=TEXT, font=(FONT_UI, 10))
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure(
            "Console.TEntry",
            fieldbackground=SURFACE_2,
            foreground=TEXT,
            insertcolor=TEXT,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
            padding=(10, 8),
        )
        style.map("Console.TEntry", bordercolor=[("focus", ACCENT)])
        style.configure(
            "Console.TCombobox",
            fieldbackground=SURFACE_2,
            background=SURFACE_2,
            foreground=TEXT,
            arrowcolor=ACCENT,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
            padding=(8, 7),
        )
        style.map(
            "Console.TCombobox",
            fieldbackground=[("readonly", SURFACE_2)],
            foreground=[("readonly", TEXT)],
            selectbackground=[("readonly", SURFACE_2)],
            selectforeground=[("readonly", TEXT)],
            bordercolor=[("focus", ACCENT)],
        )
        style.configure(
            "Console.Treeview",
            background=SURFACE,
            fieldbackground=SURFACE,
            foreground=TEXT,
            rowheight=35,
            borderwidth=0,
            relief="flat",
            font=(FONT_UI, 9),
        )
        style.configure(
            "Console.Treeview.Heading",
            background=SURFACE_2,
            foreground=MUTED,
            relief="flat",
            padding=(10, 9),
            font=(FONT_UI, 8, "bold"),
        )
        style.map(
            "Console.Treeview",
            background=[("selected", "#173A39")],
            foreground=[("selected", TEXT)],
        )
        style.map("Console.Treeview.Heading", background=[("active", SURFACE_3)])
        style.configure(
            "Vertical.TScrollbar",
            background=SURFACE_3,
            troughcolor=BG,
            bordercolor=BG,
            arrowcolor=MUTED,
        )

    def _build_shell(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()

        content = tk.Frame(self, bg=BG)
        content.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 20))
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(3, weight=1)

        self._build_scope(content)
        self._build_snapshot_cards(content)
        self._build_command_bar(content)
        self._build_results(content)
        self._build_footer()

    def _build_header(self):
        header = tk.Frame(self, bg=BG)
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 14))
        header.grid_columnconfigure(0, weight=1)

        brand = tk.Frame(header, bg=BG)
        brand.grid(row=0, column=0, sticky="w")
        brand_line = tk.Frame(brand, bg=ACCENT, width=4, height=52)
        brand_line.pack(side="left", fill="y", padx=(0, 13))
        copy = tk.Frame(brand, bg=BG)
        copy.pack(side="left")
        top = tk.Frame(copy, bg=BG)
        top.pack(anchor="w")
        tk.Label(
            top,
            text="INSTALLTRACE",
            bg=BG,
            fg=TEXT,
            font=(FONT_UI, 13, "bold"),
        ).pack(side="left")
        _chip(top, "V0.2  MIDNIGHT", fg=ACCENT, bg=ACCENT_DARK).pack(side="left", padx=(10, 0))
        tk.Label(
            copy,
            text="Installation observability, without guesswork.",
            bg=BG,
            fg=MUTED,
            font=(FONT_UI, 10),
        ).pack(anchor="w", pady=(4, 0))

        meta = tk.Frame(header, bg=BG)
        meta.grid(row=0, column=1, sticky="e")
        self.mode_chip = _chip(meta, "LOCAL / READ-ONLY", fg=BLUE, bg=BLUE_DARK)
        self.mode_chip.pack(side="right")
        tk.Label(
            meta,
            text="FILES  ·  REGISTRY  ·  SERVICES  ·  TASKS",
            bg=BG,
            fg=MUTED_2,
            font=(FONT_UI, 8, "bold"),
        ).pack(side="right", padx=(0, 12))

        divider = tk.Frame(self, bg=BORDER_SOFT, height=1)
        divider.grid(row=0, column=0, sticky="sew", padx=24)

    def _section_title(self, parent, eyebrow, title, subtitle=None):
        row = tk.Frame(parent, bg=BG)
        tk.Label(row, text=eyebrow.upper(), bg=BG, fg=ACCENT, font=(FONT_UI, 8, "bold")).pack(anchor="w")
        tk.Label(row, text=title, bg=BG, fg=TEXT, font=(FONT_UI, 15, "bold")).pack(anchor="w", pady=(2, 0))
        if subtitle:
            tk.Label(row, text=subtitle, bg=BG, fg=MUTED, font=(FONT_UI, 9)).pack(anchor="w", pady=(2, 0))
        return row

    def _build_scope(self, parent):
        scope = tk.Frame(parent, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER_SOFT)
        scope.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        scope.grid_columnconfigure(0, weight=1)

        left = tk.Frame(scope, bg=SURFACE)
        left.grid(row=0, column=0, sticky="nsew", padx=17, pady=14)
        tk.Label(left, text="SCAN SCOPE", bg=SURFACE, fg=ACCENT, font=(FONT_UI, 8, "bold")).pack(anchor="w")
        tk.Label(
            left,
            text="Paths monitored across each snapshot",
            bg=SURFACE,
            fg=TEXT,
            font=(FONT_UI, 11, "bold"),
        ).pack(anchor="w", pady=(2, 7))

        self.roots = tk.Text(
            left,
            height=3,
            bg=SURFACE_2,
            fg=TEXT,
            insertbackground=ACCENT,
            selectbackground="#1E514A",
            selectforeground=TEXT,
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
            font=(FONT_MONO, 9),
            padx=10,
            pady=8,
        )
        self.roots.pack(fill="x")
        self.roots.insert(
            "1.0",
            "\n".join(default_roots()) if os.name == "nt" else "/demo — live capture requires Windows",
        )

        controls = tk.Frame(scope, bg=SURFACE)
        controls.grid(row=0, column=1, sticky="nsew", padx=(0, 17), pady=14)
        tk.Label(controls, text="CAPTURE PROFILE", bg=SURFACE, fg=MUTED, font=(FONT_UI, 8, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
        tk.Label(controls, text="Hash up to", bg=SURFACE, fg=TEXT, font=(FONT_UI, 9)).grid(row=1, column=0, sticky="w", pady=(8, 5))
        self.hash_mb = tk.StringVar(value="16")
        hash_entry = ttk.Entry(controls, textvariable=self.hash_mb, width=7, style="Console.TEntry")
        hash_entry.grid(row=1, column=1, sticky="e", padx=(10, 0), pady=(8, 5))
        tk.Label(controls, text="MiB / file", bg=SURFACE, fg=MUTED_2, font=(FONT_UI, 8)).grid(row=2, column=0, columnspan=2, sticky="w")
        _button(controls, "+  ADD FOLDER", self.add_folder, compact=True, width=12).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(10, 5))
        _button(controls, "LOAD DEMO", self.demo, compact=True, width=12).grid(row=4, column=0, columnspan=2, sticky="ew")

    def _build_snapshot_cards(self, parent):
        wrap = tk.Frame(parent, bg=BG)
        wrap.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        for i in range(3):
            wrap.grid_columnconfigure(i, weight=1, uniform="snap")

        self.slot_labels = {}
        self.slot_state = {}
        cards = [
            ("baseline", "01", "BEFORE INSTALL", "Create the clean reference point."),
            ("installed", "02", "AFTER INSTALL", "Capture what the installer changed."),
            ("uninstalled", "03", "AFTER UNINSTALL", "Reveal persistence and leftovers."),
        ]
        for index, (key, number, title, subtitle) in enumerate(cards):
            card = tk.Frame(wrap, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER_SOFT)
            card.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else 6, 0 if index == 2 else 6))
            card.grid_columnconfigure(0, weight=1)

            top = tk.Frame(card, bg=SURFACE)
            top.grid(row=0, column=0, sticky="ew", padx=16, pady=(15, 4))
            tk.Label(top, text=number, bg=SURFACE, fg=ACCENT, font=(FONT_MONO, 10, "bold")).pack(side="left")
            state = _chip(top, "EMPTY", fg=MUTED, bg=SURFACE_2)
            state.pack(side="right")
            self.slot_state[key] = state

            tk.Label(card, text=title, bg=SURFACE, fg=TEXT, font=(FONT_UI, 11, "bold")).grid(row=1, column=0, sticky="w", padx=16)
            tk.Label(card, text=subtitle, bg=SURFACE, fg=MUTED, font=(FONT_UI, 9)).grid(row=2, column=0, sticky="w", padx=16, pady=(3, 11))

            actions = tk.Frame(card, bg=SURFACE)
            actions.grid(row=3, column=0, sticky="ew", padx=16)
            _button(actions, "CAPTURE", lambda k=key: self.capture_slot(k), primary=(key == "baseline"), compact=True).pack(side="left")
            _button(actions, "OPEN FILE", lambda k=key: self.open_slot(k), compact=True).pack(side="left", padx=(7, 0))

            label = tk.Label(card, text="No snapshot loaded", bg=SURFACE, fg=MUTED_2, font=(FONT_MONO, 8), anchor="w")
            label.grid(row=4, column=0, sticky="ew", padx=16, pady=(12, 15))
            self.slot_labels[key] = label

    def _build_command_bar(self, parent):
        bar = tk.Frame(parent, bg=SURFACE_2, highlightthickness=1, highlightbackground=BORDER)
        bar.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        bar.grid_columnconfigure(1, weight=1)

        actions = tk.Frame(bar, bg=SURFACE_2)
        actions.grid(row=0, column=0, sticky="w", padx=12, pady=10)
        _button(actions, "COMPARE INSTALL", self.compare, primary=True).pack(side="left")
        _button(actions, "FIND LEFTOVERS", lambda: self.compare(True)).pack(side="left", padx=(7, 0))
        _button(actions, "EXPORT REPORT", self.export).pack(side="left", padx=(7, 0))

        self.summary = tk.Label(
            bar,
            text="Capture or load Before + After snapshots to begin.",
            bg=SURFACE_2,
            fg=MUTED,
            font=(FONT_UI, 9),
            anchor="e",
        )
        self.summary.grid(row=0, column=1, sticky="ew", padx=12)

        self.cancel_btn = _button(bar, "CANCEL", self.cancel.set, danger=True, compact=True)
        self.cancel_btn.grid(row=0, column=2, sticky="e", padx=(0, 12), pady=10)

    def _build_results(self, parent):
        area = tk.Frame(parent, bg=BG)
        area.grid(row=3, column=0, sticky="nsew")
        area.grid_columnconfigure(0, weight=1)
        area.grid_rowconfigure(1, weight=1)

        head = tk.Frame(area, bg=BG)
        head.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        head.grid_columnconfigure(1, weight=1)

        title = self._section_title(head, "Change intelligence", "Comparison results")
        title.grid(row=0, column=0, sticky="w")

        filters = tk.Frame(head, bg=BG)
        filters.grid(row=0, column=1, sticky="e")
        self.search = tk.StringVar()
        self.search.trace_add("write", lambda *_: self.render())
        search_entry = ttk.Entry(filters, textvariable=self.search, width=26, style="Console.TEntry")
        search_entry.pack(side="left")
        self.kind = tk.StringVar(value="all")
        self.kind.trace_add("write", lambda *_: self.render())
        ttk.Combobox(
            filters,
            textvariable=self.kind,
            values=["all", "added", "modified", "removed", "uncertain"],
            state="readonly",
            width=11,
            style="Console.TCombobox",
        ).pack(side="left", padx=(7, 0))
        self.category = tk.StringVar(value="all")
        self.category.trace_add("write", lambda *_: self.render())
        ttk.Combobox(
            filters,
            textvariable=self.category,
            values=["all", *core.CATEGORIES],
            state="readonly",
            width=12,
            style="Console.TCombobox",
        ).pack(side="left", padx=(7, 0))

        panel = tk.Frame(area, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER_SOFT)
        panel.grid(row=1, column=0, sticky="nsew")
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(0, weight=3)
        panel.grid_rowconfigure(2, weight=1)

        table = tk.Frame(panel, bg=SURFACE)
        table.grid(row=0, column=0, sticky="nsew")
        table.grid_columnconfigure(0, weight=1)
        table.grid_rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(
            table,
            columns=("kind", "category", "key", "priority"),
            show="headings",
            style="Console.Treeview",
            height=8,
        )
        columns = [
            ("kind", "CHANGE", 105, False),
            ("category", "CATEGORY", 105, False),
            ("key", "RESOURCE / KEY", 640, True),
            ("priority", "TRIAGE", 155, False),
        ]
        for col, label, width, stretch in columns:
            self.tree.heading(col, text=label)
            self.tree.column(col, width=width, minwidth=70, stretch=stretch)
        scroll = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.bind("<<TreeviewSelect>>", self.details)
        self.tree.tag_configure("added", foreground=SUCCESS)
        self.tree.tag_configure("modified", foreground=BLUE)
        self.tree.tag_configure("removed", foreground=RED)
        self.tree.tag_configure("uncertain", foreground=AMBER)

        sep = tk.Frame(panel, bg=BORDER_SOFT, height=1)
        sep.grid(row=1, column=0, sticky="ew")

        detail_wrap = tk.Frame(panel, bg=SURFACE_2)
        detail_wrap.grid(row=2, column=0, sticky="nsew")
        detail_wrap.grid_columnconfigure(0, weight=1)
        detail_wrap.grid_rowconfigure(1, weight=1)
        detail_header = tk.Frame(detail_wrap, bg=SURFACE_2)
        detail_header.grid(row=0, column=0, sticky="ew", padx=13, pady=(9, 5))
        tk.Label(detail_header, text="INSPECTOR", bg=SURFACE_2, fg=MUTED, font=(FONT_UI, 8, "bold")).pack(side="left")
        self.inspect_chip = _chip(detail_header, "NO SELECTION", fg=MUTED, bg=SURFACE_3)
        self.inspect_chip.pack(side="right")
        self.detail = tk.Text(
            detail_wrap,
            height=7,
            bg=SURFACE_2,
            fg="#C6D3E1",
            insertbackground=TEXT,
            selectbackground="#214E4A",
            relief="flat",
            wrap="word",
            font=(FONT_MONO, 9),
            padx=13,
            pady=5,
            state="disabled",
        )
        self.detail.grid(row=1, column=0, sticky="nsew")
        self.show_text("Select a change to inspect the before/after values and evidence context.")

    def _build_footer(self):
        footer = tk.Frame(self, bg=BG)
        footer.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 13))
        footer.grid_columnconfigure(1, weight=1)
        self.status_dot = tk.Label(footer, text="●", bg=BG, fg=SUCCESS, font=(FONT_UI, 8))
        self.status_dot.grid(row=0, column=0, sticky="w")
        self.status = tk.StringVar(value="Ready. Read-only inspection; no automatic deletion or installer execution.")
        tk.Label(
            footer,
            textvariable=self.status,
            bg=BG,
            fg=MUTED,
            font=(FONT_UI, 8),
            anchor="w",
        ).grid(row=0, column=1, sticky="ew", padx=(7, 0))
        tk.Label(
            footer,
            text="INSTALLTRACE / 0.2.0",
            bg=BG,
            fg=MUTED_2,
            font=(FONT_MONO, 8),
        ).grid(row=0, column=2, sticky="e")

    # ---------- state helpers ----------
    def _set_busy(self, busy, text=None):
        self.busy = busy
        self.status_dot.configure(fg=AMBER if busy else SUCCESS)
        self.mode_chip.configure(
            text="CAPTURING" if busy else "LOCAL / READ-ONLY",
            fg=AMBER if busy else BLUE,
            bg=AMBER_DARK if busy else BLUE_DARK,
        )
        if text:
            self.status.set(text)

    # ---------- actions ----------
    def add_folder(self):
        if self.busy:
            return
        path = filedialog.askdirectory()
        if path:
            current = self.roots.get("1.0", "end").strip()
            self.roots.insert("end", ("\n" if current else "") + path)

    def set_snapshot(self, key, value):
        self.snapshots[key] = value
        gaps = sum(s["status"] != "complete" for s in value["sections"].values())
        count = sum(len(s["records"]) for s in value["sections"].values())
        self.slot_labels[key].configure(text=f"{count:,} records   /   {gaps} coverage gaps", fg=TEXT if gaps == 0 else AMBER)
        self.slot_state[key].configure(
            text="READY" if gaps == 0 else "PARTIAL",
            fg=SUCCESS if gaps == 0 else AMBER,
            bg="#12372D" if gaps == 0 else AMBER_DARK,
        )
        self.result = None
        self.render()
        self.summary.configure(text="Snapshots updated. Run a comparison to refresh change intelligence.", fg=MUTED)
        self.show_text(
            json.dumps(
                {
                    "created": value.get("created"),
                    "scope": value["scope"],
                    "coverage": {
                        k: {"status": v["status"], "errors": v["errors"]}
                        for k, v in value["sections"].items()
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        self.inspect_chip.configure(text="SNAPSHOT", fg=BLUE, bg=BLUE_DARK)

    def open_slot(self, key):
        if self.busy:
            return
        path = filedialog.askopenfilename(filetypes=[("InstallTrace snapshot", "*.json")])
        if path:
            try:
                self.set_snapshot(key, core.load(path))
            except Exception as exc:
                messagebox.showerror("Cannot load snapshot", str(exc))

    def capture_slot(self, key):
        if self.busy:
            return
        if os.name != "nt":
            messagebox.showinfo("Windows capture", "Use Load demo here. Live capture requires Windows 10/11.")
            return
        try:
            limit = int(self.hash_mb.get())
            if not 0 <= limit <= 1024:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Hash limit", "Enter an integer from 0 to 1024.")
            return
        roots = [x.strip() for x in self.roots.get("1.0", "end").splitlines() if x.strip()]
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            initialfile=key + ".json",
            filetypes=[("Snapshot", "*.json")],
        )
        if not path:
            return

        self.cancel.clear()
        self._set_busy(True, "Capturing snapshot — keep the machine idle until the scan finishes.")
        self.slot_state[key].configure(text="SCANNING", fg=AMBER, bg=AMBER_DARK)

        def work():
            try:
                data = capture(roots, limit, self.cancel, lambda msg: self.events.put(("status", msg)))
                core.save(path, data)
                self.events.put(("done", (key, data)))
            except Exception as exc:
                self.events.put(("error", (key, str(exc))))

        threading.Thread(target=work, daemon=True).start()

    def poll(self):
        try:
            while True:
                event, payload = self.events.get_nowait()
                if event == "status":
                    self.status.set(payload)
                elif event == "done":
                    self._set_busy(False)
                    self.set_snapshot(*payload)
                    self.status.set("Snapshot saved. Check coverage before interpreting results.")
                else:
                    key, message = payload
                    self._set_busy(False, message)
                    self.slot_state[key].configure(text="EMPTY", fg=MUTED, bg=SURFACE_2)
                    messagebox.showinfo("Capture stopped", message)
        except queue.Empty:
            pass
        self.after(100, self.poll)

    def demo(self):
        if self.busy:
            return
        for key, data in zip(("baseline", "installed", "uninstalled"), samples()):
            self.set_snapshot(key, data)
        self.compare()
        self.status.set("DEMO MODE — synthetic records only; no scan of your computer was performed.")
        self.mode_chip.configure(text="DEMO DATA", fg=PURPLE, bg=PURPLE_DARK)

    def compare(self, uninstall=False):
        if self.busy:
            return
        try:
            a, b = self.snapshots["baseline"], self.snapshots["installed"]
            self.result = (
                core.leftovers(a, b, self.snapshots["uninstalled"])
                if uninstall
                else core.compare(a, b)
            )
        except KeyError:
            messagebox.showinfo(
                "Snapshots needed",
                "Load Before and After install snapshots; leftovers also needs After uninstall.",
            )
            return
        except ValueError as exc:
            messagebox.showerror("Cannot compare", str(exc))
            return

        counts = Counter(c["kind"] for c in self.result["changes"])
        mode = self.result["mode"].replace("_", " ").upper()
        self.summary.configure(
            text=(
                f"{mode}  ·  {counts['added']} added  ·  {counts['modified']} modified  ·  "
                f"{counts['removed']} removed  ·  {counts['uncertain']} uncertain"
            ),
            fg=TEXT,
        )
        self.render()
        self.show_text(
            "\n".join(self.result["warnings"])
            or "Select a row to inspect before and after values.\nPersistence is a triage label, not a malware verdict."
        )
        self.inspect_chip.configure(text="SUMMARY", fg=ACCENT, bg=ACCENT_DARK)
        self.status.set(f"Comparison complete — {len(self.result['changes']):,} changes in the current result set.")

    def render(self):
        if not hasattr(self, "tree"):
            return
        self.tree.delete(*self.tree.get_children())
        self.rows = []
        if not self.result:
            return
        query = self.search.get().casefold().strip()
        for change in self.result["changes"]:
            if self.kind.get() != "all" and change["kind"] != self.kind.get():
                continue
            if self.category.get() != "all" and change["category"] != self.category.get():
                continue
            if query and query not in json.dumps(change, ensure_ascii=False).casefold():
                continue
            self.rows.append(change)
            row_id = str(len(self.rows) - 1)
            self.tree.insert(
                "",
                "end",
                iid=row_id,
                values=(change["kind"].upper(), change["category"], change["key"], change["priority"]),
                tags=(change["kind"],),
            )

    def show_text(self, text):
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert("1.0", text)
        self.detail.configure(state="disabled")

    def details(self, _=None):
        selected = self.tree.selection()
        if selected:
            row = self.rows[int(selected[0])]
            self.show_text(json.dumps(row, ensure_ascii=False, indent=2))
            kind = row.get("kind", "change").upper()
            palette = {
                "ADDED": (SUCCESS, "#12372D"),
                "MODIFIED": (BLUE, BLUE_DARK),
                "REMOVED": (RED, RED_DARK),
                "UNCERTAIN": (AMBER, AMBER_DARK),
            }
            fg, bg = palette.get(kind, (MUTED, SURFACE_3))
            self.inspect_chip.configure(text=kind, fg=fg, bg=bg)

    def export(self):
        if not self.result:
            messagebox.showinfo("No report", "Run a comparison first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".html",
            initialfile="installtrace-report.html",
            filetypes=[("Offline HTML report", "*.html"), ("JSON report", "*.json")],
        )
        if path:
            try:
                if Path(path).suffix.lower() == ".json":
                    core.save(path, self.result)
                else:
                    Path(path).write_text(core.report_html(self.result), encoding="utf-8")
                self.status.set(
                    "Report exported. It can contain local paths or command arguments; review before sharing."
                )
            except OSError as exc:
                messagebox.showerror("Export failed", str(exc))

    def close(self):
        if self.busy:
            self.cancel.set()
            self.status.set("Cancelling capture. Close again after the capture stops.")
            return
        self.destroy()


def run():
    App().mainloop()
