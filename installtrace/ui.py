"""Dependency-free desktop UI; worker threads never call Tk directly."""
import json
import os
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from collections import Counter
from . import core
from .collect import capture, default_roots, Cancelled
from .demo import samples

BG = '#0d1520'
PANEL = '#162333'
TEXT = '#e0eaf5'
MUTED = '#9db0c5'
ACCENT = '#65e0b7'


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('InstallTrace — installation observability')
        self.geometry('1230x850'); self.minsize(950, 650); self.configure(bg=BG)
        self.snapshots = {}; self.result = None; self.rows = []
        self.events = queue.Queue(); self.cancel = threading.Event(); self.busy = False
        style = ttk.Style(self); style.theme_use('clam')
        style.configure('.', background=BG, foreground=TEXT, font=('Segoe UI', 10))
        style.configure('TButton', background=PANEL, foreground=TEXT, padding=(12, 8), borderwidth=0)
        style.map('TButton', background=[('active', '#294159')], foreground=[('disabled', '#6c7d90')])
        style.configure('Accent.TButton', background=ACCENT, foreground=BG)
        style.configure('TEntry', fieldbackground=PANEL, foreground=TEXT, insertcolor=TEXT)
        style.configure('TCombobox', fieldbackground=PANEL, background=PANEL, foreground=TEXT, arrowcolor=ACCENT)
        style.configure('Treeview', background=PANEL, fieldbackground=PANEL, foreground=TEXT, rowheight=32, borderwidth=0)
        style.configure('Treeview.Heading', background='#213349', foreground=TEXT, padding=7)
        style.map('Treeview', background=[('selected', '#265949')])
        header = tk.Frame(self, bg=BG); header.pack(fill='x', padx=28, pady=(22, 14))
        tk.Label(header, text='INSTALLTRACE', fg=ACCENT, bg=BG, font=('Segoe UI', 12, 'bold')).pack(anchor='w')
        tk.Label(header, text='Know what changed.', fg=TEXT, bg=BG, font=('Segoe UI', 28, 'bold')).pack(anchor='w')
        tk.Label(header, text='Local snapshots  /  Installation changes  /  Uninstall leftovers', fg=MUTED, bg=BG).pack(anchor='w', pady=(4, 0))
        controls = ttk.Frame(self); controls.pack(fill='x', padx=28)
        ttk.Label(controls, text='Folder scope (one path per line)  •  Add the app’s AppData folder for fuller coverage').pack(anchor='w')
        self.roots = tk.Text(controls, height=3, bg=PANEL, fg=TEXT, insertbackground=TEXT, relief='flat', font=('Consolas', 10))
        self.roots.pack(fill='x', pady=5)
        self.roots.insert('1.0', '\n'.join(default_roots()) if os.name == 'nt' else '/demo — live capture requires Windows')
        settings = ttk.Frame(controls); settings.pack(fill='x', pady=(0, 10))
        ttk.Button(settings, text='+ Folder', command=self.add_folder).pack(side='left')
        ttk.Label(settings, text='  Hash files up to (MiB; 0 = metadata only): ').pack(side='left')
        self.hash_mb = tk.StringVar(value='16')
        ttk.Entry(settings, textvariable=self.hash_mb, width=6).pack(side='left')
        ttk.Button(settings, text='Load demo', command=self.demo).pack(side='right')
        self.slot_labels = {}
        slots = ttk.Frame(self); slots.pack(fill='x', padx=28)
        for key, label in [('baseline', '01  Before install'), ('installed', '02  After install'), ('uninstalled', '03  After uninstall')]:
            box = ttk.Frame(slots); box.pack(side='left', fill='x', expand=True, padx=(0, 14))
            ttk.Label(box, text=label, font=('Segoe UI', 11, 'bold')).pack(anchor='w')
            line = ttk.Frame(box); line.pack(anchor='w', pady=6)
            ttk.Button(line, text='Capture', command=lambda k=key: self.capture_slot(k)).pack(side='left')
            ttk.Button(line, text='Open…', command=lambda k=key: self.open_slot(k)).pack(side='left', padx=4)
            self.slot_labels[key] = ttk.Label(box, text='No snapshot', foreground=MUTED)
            self.slot_labels[key].pack(anchor='w')
        actions = ttk.Frame(self); actions.pack(fill='x', padx=28, pady=14)
        ttk.Button(actions, text='Compare installation', style='Accent.TButton', command=self.compare).pack(side='left')
        ttk.Button(actions, text='Find leftovers', command=lambda: self.compare(True)).pack(side='left', padx=8)
        ttk.Button(actions, text='Export report…', command=self.export).pack(side='left')
        ttk.Button(actions, text='Cancel capture', command=self.cancel.set).pack(side='right')
        self.summary = ttk.Label(self, text='Load a demo, or capture a baseline before running an installer.', foreground=ACCENT)
        self.summary.pack(anchor='w', padx=28)
        filters = ttk.Frame(self); filters.pack(fill='x', padx=28, pady=10)
        ttk.Label(filters, text='Search ').pack(side='left')
        self.search = tk.StringVar(); self.search.trace_add('write', lambda *_: self.render())
        ttk.Entry(filters, textvariable=self.search, width=35).pack(side='left')
        self.kind = tk.StringVar(value='all'); self.kind.trace_add('write', lambda *_: self.render())
        ttk.Combobox(filters, textvariable=self.kind, values=['all','added','modified','removed','uncertain'], state='readonly', width=13).pack(side='left', padx=10)
        self.category = tk.StringVar(value='all'); self.category.trace_add('write', lambda *_: self.render())
        ttk.Combobox(filters, textvariable=self.category, values=['all', *core.CATEGORIES], state='readonly', width=13).pack(side='left')
        body = ttk.Panedwindow(self, orient='vertical'); body.pack(fill='both', expand=True, padx=28)
        table = ttk.Frame(body); body.add(table, weight=3)
        self.tree = ttk.Treeview(table, columns=('kind','category','key','priority'), show='headings', height=8)
        for col, width in [('kind',95),('category',90),('key',610),('priority',155)]:
            self.tree.heading(col, text=col.title()); self.tree.column(col, width=width, minwidth=60, stretch=(col=='key'))
        scroll = ttk.Scrollbar(table, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set); scroll.pack(side='right', fill='y'); self.tree.pack(fill='both', expand=True)
        self.tree.bind('<<TreeviewSelect>>', self.details)
        self.detail = tk.Text(body, height=7, bg=PANEL, fg=TEXT, relief='flat', wrap='word', font=('Consolas', 10), state='disabled')
        body.add(self.detail, weight=2)
        self.status = tk.StringVar(value='Read-only inspection. State differences do not prove installer attribution or malware.')
        ttk.Label(self, textvariable=self.status, wraplength=1150, foreground=MUTED).pack(fill='x', padx=28, pady=12)
        self.after(100, self.poll)
        self.protocol('WM_DELETE_WINDOW', self.close)

    def add_folder(self):
        if self.busy: return
        path = filedialog.askdirectory()
        if path: self.roots.insert('end', '\n' + path)

    def set_snapshot(self, key, value):
        self.snapshots[key] = value
        gaps = sum(s['status'] != 'complete' for s in value['sections'].values())
        count = sum(len(s['records']) for s in value['sections'].values())
        self.slot_labels[key].configure(text=f'{count:,} records · {gaps} coverage gaps')
        self.result = None; self.render()
        self.summary.configure(text='Snapshots updated. Compare to refresh results.')
        self.show_text(json.dumps({'created': value.get('created'), 'scope': value['scope'], 'coverage': {k: {'status': v['status'], 'errors': v['errors']} for k,v in value['sections'].items()}}, ensure_ascii=False, indent=2))

    def open_slot(self, key):
        if self.busy: return
        path = filedialog.askopenfilename(filetypes=[('InstallTrace snapshot','*.json')])
        if path:
            try: self.set_snapshot(key, core.load(path))
            except Exception as exc: messagebox.showerror('Cannot load snapshot', str(exc))

    def capture_slot(self, key):
        if self.busy: return
        if os.name != 'nt':
            messagebox.showinfo('Windows capture', 'Use Load demo here. Live capture requires Windows 10/11.'); return
        try:
            limit = int(self.hash_mb.get())
            if not 0 <= limit <= 1024: raise ValueError()
        except ValueError:
            messagebox.showerror('Hash limit', 'Enter an integer from 0 to 1024.'); return
        roots = self.roots.get('1.0','end').strip().splitlines()
        path = filedialog.asksaveasfilename(defaultextension='.json', initialfile=key+'.json', filetypes=[('Snapshot','*.json')])
        if not path: return
        # Captures are saved only after scanning; place them outside scanned folders to avoid self-noise.
        self.busy = True; self.cancel.clear(); self.status.set('Capturing — keep the machine idle until finished.')
        def work():
            try:
                data = capture(roots, limit, self.cancel, lambda msg: self.events.put(('status', msg)))
                core.save(path, data); self.events.put(('done', (key, data)))
            except Exception as exc: self.events.put(('error', str(exc)))
        threading.Thread(target=work, daemon=True).start()

    def poll(self):
        try:
            while True:
                event, payload = self.events.get_nowait()
                if event == 'status': self.status.set(payload)
                elif event == 'done':
                    self.busy = False; self.set_snapshot(*payload); self.status.set('Snapshot saved. Check coverage details before interpreting results.')
                else:
                    self.busy = False; self.status.set(payload); messagebox.showinfo('Capture stopped', payload)
        except queue.Empty: pass
        self.after(100, self.poll)

    def demo(self):
        if self.busy: return
        for key, data in zip(('baseline','installed','uninstalled'), samples()): self.set_snapshot(key, data)
        self.compare(); self.status.set('DEMO — synthetic records, not a scan of your computer.')

    def compare(self, uninstall=False):
        if self.busy: return
        try:
            a, b = self.snapshots['baseline'], self.snapshots['installed']
            self.result = core.leftovers(a, b, self.snapshots['uninstalled']) if uninstall else core.compare(a,b)
        except KeyError:
            messagebox.showinfo('Snapshots needed', 'Load Before and After install snapshots; leftovers also needs After uninstall.'); return
        except ValueError as exc:
            messagebox.showerror('Cannot compare', str(exc)); return
        counts = Counter(c['kind'] for c in self.result['changes'])
        self.summary.configure(text=f'{self.result["mode"].title()}   /   ' + '   ·   '.join(f'{counts[k]} {k}' for k in ('added','modified','removed','uncertain')))
        self.render(); self.show_text('\n'.join(self.result['warnings']) or 'Select a row to inspect before and after values.\nReview persistence is a triage label, not a malware verdict.')

    def render(self):
        if not hasattr(self, 'tree'): return
        self.tree.delete(*self.tree.get_children()); self.rows = []
        if not self.result: return
        for c in self.result['changes']:
            if self.kind.get() != 'all' and c['kind'] != self.kind.get(): continue
            if self.category.get() != 'all' and c['category'] != self.category.get(): continue
            if self.search.get().casefold() not in json.dumps(c, ensure_ascii=False).casefold(): continue
            self.rows.append(c)
            self.tree.insert('', 'end', iid=str(len(self.rows)-1), values=(c['kind'], c['category'], c['key'], c['priority']))

    def show_text(self, text):
        self.detail.configure(state='normal'); self.detail.delete('1.0','end'); self.detail.insert('1.0',text); self.detail.configure(state='disabled')

    def details(self, _=None):
        selected = self.tree.selection()
        if selected: self.show_text(json.dumps(self.rows[int(selected[0])], ensure_ascii=False, indent=2))

    def export(self):
        if not self.result:
            messagebox.showinfo('No report', 'Run a comparison first.'); return
        path = filedialog.asksaveasfilename(defaultextension='.html', initialfile='installtrace-report.html', filetypes=[('Offline HTML report','*.html'),('JSON report','*.json')])
        if path:
            try:
                if Path(path).suffix.lower() == '.json': core.save(path, self.result)
                else: Path(path).write_text(core.report_html(self.result), encoding='utf-8')
                self.status.set('Report exported. Contains local paths and possibly private command arguments; review before sharing.')
            except OSError as exc: messagebox.showerror('Export failed', str(exc))

    def close(self):
        if self.busy:
            self.cancel.set(); self.status.set('Cancelling capture. Close again after capture stops.'); return
        self.destroy()


def run():
    App().mainloop()
