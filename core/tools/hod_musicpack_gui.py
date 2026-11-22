"""Harmony of Despair Music Pack Builder: a window around hod_musicpack.py.

Add songs (audio files, or ready-made Xbox 360 .xwb banks), give each a title,
check or drag its loop points on the waveform, listen to the loop seam, pick
the DLC package number, then Build or Install. Packs are saved as the same
pack.json files the command-line tool reads.

Start it with "HoD Music Pack Builder.bat" or: pythonw hod_musicpack_gui.py
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import contextlib
import json
import queue
import shutil
import sys
import tempfile
import threading
import traceback
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:  # crisp text on high-DPI screens instead of a stretched bitmap
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except (ImportError, AttributeError, OSError):
    pass

MISSING = []
try:
    import numpy as np
except ImportError:
    MISSING.append('numpy')
try:
    import soundfile  # noqa: F401
except ImportError:
    MISSING.append('soundfile')
try:
    import soxr  # noqa: F401
except ImportError:
    MISSING.append('soxr')

if not MISSING:
    import hod_musicpack as mp

OFFICIAL = {1: 'Pyramid stage', 2: 'Legion stage', 3: 'stage DLC', 4: 'Origins stage',
            7: 'Getsu Fuma stage', 11: 'Julius', 12: 'Maria', 13: 'Richter', 14: 'Yoko',
            15: 'Simon (8-bit)', 16: 'Getsu Fuma (8-bit)', 17: 'Nathan (mod)',
            28: 'BGM pack 1', 29: 'Music pack 2'}
ENV_BINS = 2000


RATE_AUTO = 'Best that fits the size limit'
FIXED_RATES = (48000, 44100, 32000, 24000, 22050)


def fmt_time(s):
    return f'{int(s // 60)}:{s % 60:06.3f}'


def parse_time(text):
    """'67.01', '1:07.01' -> seconds."""
    text = text.strip()
    if ':' in text:
        m, s = text.split(':', 1)
        return int(m) * 60 + float(s)
    return float(text)


class QueueWriter:
    def __init__(self, q):
        self.q = q

    def write(self, text):
        if text:
            self.q.put(('log', text))

    def flush(self):
        pass


class Waveform(tk.Canvas):
    """Envelope of a track with draggable loop start (green) and end (red)."""

    def __init__(self, master, on_change, height=150):
        super().__init__(master, height=height, background='#1e1e24', highlightthickness=0)
        self.on_change = on_change
        self.env = None
        self.duration = 0.0
        self.start = self.end = None
        self.drag = None
        self.message = 'Select a track'
        self.bind('<Configure>', lambda e: self.redraw())
        self.bind('<ButtonPress-1>', self._press)
        self.bind('<B1-Motion>', self._motion)
        self.bind('<ButtonRelease-1>', self._release)

    def show(self, env, duration, start, end, message=''):
        self.env, self.duration, self.start, self.end, self.message = env, duration, start, end, message
        self.redraw()

    def _x(self, t):
        w = max(1, self.winfo_width() - 20)
        return 10 + w * t / self.duration if self.duration else 10

    def _t(self, x):
        w = max(1, self.winfo_width() - 20)
        return min(max((x - 10) / w * self.duration, 0.0), self.duration)

    def redraw(self):
        self.delete('all')
        w, h = self.winfo_width(), self.winfo_height()
        if self.env is None:
            self.create_text(w / 2, h / 2, text=self.message, fill='#9a9aa8', font=('Segoe UI', 10))
            return
        lo, hi = self.env
        mid, amp = (h - 18) / 2, (h - 22) / 2
        if self.start is not None and self.end is not None:
            self.create_rectangle(self._x(self.start), 0, self._x(self.end), h - 16,
                                  fill='#2c3a48', outline='')
        cols = max(1, w - 20)
        key = (id(self.env), cols)
        if getattr(self, '_cols_key', None) != key:  # per-column envelope, cached per width
            idx = (np.arange(cols + 1) * len(lo) / cols).astype(int)
            idx[1:] = np.maximum(idx[1:], idx[:-1] + 1)
            idx = np.minimum(idx, len(lo))
            self._cols = [(hi[a:b].max(), lo[a:b].min()) if b > a else (0.0, 0.0)
                          for a, b in zip(idx[:-1], idx[1:])]
            self._cols_key = key
        cut = self._x(self.end) - 10 if self.end is not None else cols  # audio after the loop end is dropped
        for c, (top, bot) in enumerate(self._cols):
            self.create_line(10 + c, mid - top * amp, 10 + c, mid - bot * amp + 1,
                             fill='#7fb2e5' if c <= cut else '#3d4652')
        if self.end is not None and self.duration - self.end > 0.5:
            self.create_text((self._x(self.end) + w - 10) / 2, h - 26, text='not kept (never played)',
                             fill='#7d8592', font=('Segoe UI', 8))
        step = 10 if self.duration < 200 else 30
        t = 0
        while t <= self.duration:
            x = self._x(t)
            self.create_line(x, h - 16, x, h - 12, fill='#9a9aa8')
            anchor = 'w' if x < 30 else 'e' if x > w - 30 else 'center'  # keep edge labels inside
            self.create_text(x, h - 6, text=f'{int(t // 60)}:{int(t % 60):02d}', fill='#9a9aa8',
                             font=('Segoe UI', 7), anchor=anchor)
            t += step
        for t, color, label in ((self.start, '#58d68d', 'loop start'), (self.end, '#ec7063', 'loop end')):
            if t is not None:
                x = self._x(t)
                self.create_line(x, 0, x, h - 16, fill=color, width=2)
                self.create_text(x + 4, 8, text=label, fill=color, anchor='w', font=('Segoe UI', 8))
        if self.message:
            self.create_text(w - 8, 8, text=self.message, fill='#c8c8d0', anchor='e', font=('Segoe UI', 8))

    def _press(self, e):
        if self.env is None or self.start is None:
            return
        ds, de = abs(e.x - self._x(self.start)), abs(e.x - self._x(self.end))
        if min(ds, de) <= 8:
            self.drag = 'start' if ds <= de else 'end'

    def _motion(self, e):
        if not self.drag:
            return
        t = self._t(e.x)
        if self.drag == 'start':
            self.start = min(t, self.end - 0.05)
        else:
            self.end = max(t, self.start + 0.05)
        self.redraw()

    def _release(self, e):
        if self.drag:
            self.drag = None
            self.on_change(self.start, self.end)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('HoD Music Pack Builder')
        self.ui = max(1.0, self.winfo_fpixels('1i') / 96)  # screen scale (1.0 at 100%)
        self.geometry(f'{self.px(1040)}x{self.px(760)}')
        self.minsize(self.px(860), self.px(640))
        self.q = queue.Queue()
        self.tracks = []          # pack.json track dicts (+ private '_env', '_dur', '_status')
        self.pack_path = None
        self.busy = False
        self.selected = None
        self.extra = {}           # pack keys the window does not edit, kept on save
        if sys.stdout is None:    # the bundled .exe has no console: send prints to the log
            sys.stdout = QueueWriter(self.q)
        if sys.stderr is None:
            sys.stderr = QueueWriter(self.q)
        self.settings = self._load_settings()
        self.game = self._find_game()
        self._build_ui()
        self.after(100, self._poll)
        self._update_package_status()
        self._update_game_status()

    def px(self, n):
        return int(n * self.ui)

    # ---------------------------------------------------------- settings --
    SETTINGS = Path.home() / 'AppData/Roaming/HoD Music Pack Builder/settings.json'

    def _load_settings(self):
        try:
            return json.loads(self.SETTINGS.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return {}

    def _save_settings(self):
        try:
            self.SETTINGS.parent.mkdir(parents=True, exist_ok=True)
            self.SETTINGS.write_text(json.dumps(self.settings, indent=2), encoding='utf-8')
        except OSError:
            pass

    def _find_game(self):
        """Saved choice, else the folder this tool sits in (if it is the game's)."""
        for candidate in (self.settings.get('game'), mp.ROOT, mp.ROOT.parent):
            if candidate and mp.is_game_folder(candidate):
                return Path(candidate)
        return None

    def choose_game(self):
        d = filedialog.askdirectory(title='HarmonyRecomp folder (the one with harmonyrecomp.exe)',
                                    initialdir=str(self.game or Path.home()))
        if not d:
            return
        if not mp.is_game_folder(d):
            messagebox.showerror('HarmonyRecomp folder',
                                 'That folder has no harmonyrecomp.exe and dlc_packages.txt.\n\n'
                                 'Choose the folder HarmonyRecomp was installed to. dlc_packages.txt is '
                                 'written by its setup when it is built with your DLC.')
            return
        self.game = Path(d)
        self.settings['game'] = str(self.game)
        self._save_settings()
        self._update_game_status()

    def _update_game_status(self):
        if self.game:
            self.game_var.set(str(self.game))
            self.game_status.configure(text='', foreground='#1e8449')
        else:
            self.game_var.set('')
            self.game_status.configure(text='Choose it to install packs', foreground='#b03a2e')
        if hasattr(self, 'pkg_status'):
            self._update_package_status()

    # ------------------------------------------------------------ layout --
    def _build_ui(self):
        style = ttk.Style(self)
        if 'vista' in style.theme_names():
            style.theme_use('vista')
        style.configure('Treeview', rowheight=self.px(22))
        top = ttk.LabelFrame(self, text='Pack', padding=8)
        top.pack(fill='x', padx=10, pady=(10, 4))
        ttk.Label(top, text='Pack name').grid(row=0, column=0, sticky='w')
        self.name_var = tk.StringVar(value='My Music Pack')
        ttk.Entry(top, textvariable=self.name_var, width=36).grid(row=0, column=1, sticky='w', padx=(6, 18))
        ttk.Label(top, text='DLC package number').grid(row=0, column=2, sticky='w')
        self.pkg_var = tk.StringVar(value=str(self._first_free()))
        pkg = ttk.Spinbox(top, from_=1, to=63, textvariable=self.pkg_var, width=5,
                          command=self._update_package_status)
        pkg.grid(row=0, column=3, sticky='w', padx=6)
        pkg.bind('<KeyRelease>', lambda e: self._update_package_status())
        self.pkg_status = ttk.Label(top, text='', width=46)
        self.pkg_status.grid(row=0, column=4, sticky='w')
        ttk.Label(top, text='HarmonyRecomp folder').grid(row=2, column=0, sticky='w', pady=(6, 0))
        self.game_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.game_var, state='readonly').grid(
            row=2, column=1, columnspan=2, sticky='we', padx=(6, 6), pady=(6, 0))
        ttk.Button(top, text='Browse...', command=self.choose_game).grid(row=2, column=3, sticky='w',
                                                                         padx=6, pady=(6, 0))
        self.game_status = ttk.Label(top, text='')
        self.game_status.grid(row=2, column=4, sticky='w', pady=(6, 0))
        ttk.Label(top, text='Max size per song (MB)').grid(row=1, column=0, sticky='w', pady=(6, 0))
        self.mb_var = tk.StringVar(value=str(mp.DEFAULT_MAX_MB))
        ttk.Spinbox(top, from_=1, to=8, increment=0.5, textvariable=self.mb_var, width=6,
                    command=self._quality_changed).grid(row=1, column=1, sticky='w', padx=6, pady=(6, 0))
        self.mb_var.trace_add('write', lambda *a: self._quality_changed())
        ttk.Label(top, text='The game silently skips songs that do not fit its sound memory; '
                            '5 MB matches the largest official song.',
                  foreground='#666').grid(row=1, column=2, columnspan=3, sticky='w', pady=(6, 0))
        self.auto_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text="Match the game's music volume", variable=self.auto_var).grid(
            row=3, column=0, columnspan=2, sticky='w', pady=(6, 0))
        ttk.Label(top, text=f'Same loudness as the official music ({mp.GAME_MUSIC_LUFS} LUFS); '
                            '"Volume (dB)" fine-tunes a song on top.',
                  foreground='#666').grid(row=3, column=2, columnspan=3, sticky='w', pady=(6, 0))
        ttk.Label(top, text='Sample rate').grid(row=4, column=0, sticky='w', pady=(6, 0))
        qual = ttk.Frame(top)
        qual.grid(row=4, column=1, sticky='w', padx=6, pady=(6, 0))
        self.rate_var = tk.StringVar(value=RATE_AUTO)
        rate_box = ttk.Combobox(qual, textvariable=self.rate_var, state='readonly', width=26,
                                values=[RATE_AUTO] + [f'{r} Hz' for r in FIXED_RATES])
        rate_box.pack(side='left')
        rate_box.bind('<<ComboboxSelected>>', lambda e: self._quality_changed())
        self.mono_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(qual, text='Mono', variable=self.mono_var,
                        command=self._quality_changed).pack(side='left', padx=(10, 0))
        ttk.Label(top, text='The game keeps songs in memory as uncompressed audio (11 MB per minute '
                            'at 48000 Hz), so "best that fits" lowers the rate to stay under the size '
                            'limit. Mono doubles the rate in the same size. A fixed rate can go over '
                            'the limit, and the game may then skip the song.',
                  foreground='#666', wraplength=self.px(560)).grid(row=4, column=2, columnspan=3,
                                                                  sticky='w', pady=(6, 0))

        mid = ttk.Frame(self)
        mid.pack(fill='both', expand=True, padx=10, pady=4)
        left = ttk.LabelFrame(mid, text='Songs (in track list order)', padding=6)
        left.pack(side='left', fill='both', expand=False)
        self.tree = ttk.Treeview(left, columns=('title', 'loop', 'status'), show='headings',
                                 height=12, selectmode='browse')
        for col, text, w in (('title', 'Title', 190), ('loop', 'Loop', 150), ('status', 'Status', 110)):
            self.tree.heading(col, text=text)
            self.tree.column(col, width=self.px(w), anchor='w')
        self.tree.pack(fill='both', expand=True)
        self.tree.bind('<<TreeviewSelect>>', lambda e: self._select())
        bar = ttk.Frame(left)
        bar.pack(fill='x', pady=(6, 0))
        ttk.Button(bar, text='Add songs...', command=self.add_files).pack(side='left')
        ttk.Button(bar, text='Remove', command=self.remove).pack(side='left', padx=4)
        ttk.Button(bar, text='Up', width=5, command=lambda: self.move(-1)).pack(side='left')
        ttk.Button(bar, text='Down', width=6, command=lambda: self.move(1)).pack(side='left', padx=4)

        right = ttk.LabelFrame(mid, text='Selected song', padding=8)
        right.pack(side='left', fill='both', expand=True, padx=(10, 0))
        self.file_label = ttk.Label(right, text='', foreground='#555', wraplength=self.px(440))
        self.file_label.grid(row=0, column=0, columnspan=4, sticky='w')
        ttk.Label(right, text='Title in game').grid(row=1, column=0, sticky='w', pady=(8, 0))
        self.title_var = tk.StringVar()
        self.title_entry = ttk.Entry(right, textvariable=self.title_var, width=40)
        self.title_entry.grid(row=1, column=1, columnspan=3, sticky='we', pady=(8, 0))
        self.title_var.trace_add('write', lambda *a: self._edit_title())

        ttk.Label(right, text='Loop').grid(row=2, column=0, sticky='w', pady=(8, 0))
        self.mode_var = tk.StringVar(value='manual')
        modes = ttk.Frame(right)
        modes.grid(row=2, column=1, columnspan=3, sticky='w', pady=(8, 0))
        self.mode_buttons = []
        for value, text in (('manual', 'Loop between the markers'), ('whole', 'Loop the whole file')):
            b = ttk.Radiobutton(modes, text=text, value=value, variable=self.mode_var,
                                command=self._edit_mode)
            b.pack(side='left', padx=(0, 12))
            self.mode_buttons.append(b)
        ttk.Label(right, text='Loop start').grid(row=3, column=0, sticky='w', pady=(6, 0))
        self.start_var = tk.StringVar()
        self.start_entry = ttk.Entry(right, textvariable=self.start_var, width=12)
        self.start_entry.grid(row=3, column=1, sticky='w', pady=(6, 0))
        ttk.Label(right, text='Loop end').grid(row=3, column=2, sticky='e', pady=(6, 0))
        self.end_var = tk.StringVar()
        self.end_entry = ttk.Entry(right, textvariable=self.end_var, width=12)
        self.end_entry.grid(row=3, column=3, sticky='w', padx=6, pady=(6, 0))
        for entry in (self.start_entry, self.end_entry):
            entry.bind('<Return>', lambda e: self._edit_times())
            entry.bind('<FocusOut>', lambda e: self._edit_times())
        ttk.Label(right, text='m:ss.sss or seconds. Playback goes from the start, through the loop end, '
                              'then back to the loop start forever; audio after the loop end is dropped.',
                  foreground='#666', wraplength=self.px(440)).grid(row=4, column=0, columnspan=4, sticky='w')
        acts = ttk.Frame(right)
        acts.grid(row=5, column=0, columnspan=4, sticky='w', pady=(8, 0))
        self.detect_btn = ttk.Button(acts, text='Find loop automatically', command=self.detect)
        self.detect_btn.pack(side='left')
        self.preview_btn = ttk.Button(acts, text='Hear the loop seam', command=self.preview)
        self.preview_btn.pack(side='left', padx=6)
        self.stop_btn = ttk.Button(acts, text='Stop', command=self.stop_sound)
        self.stop_btn.pack(side='left')
        ttk.Label(right, text='Volume (dB)').grid(row=6, column=0, sticky='w', pady=(8, 0))
        self.gain_var = tk.StringVar(value='0')
        gain = ttk.Spinbox(right, from_=-20, to=20, increment=0.5, textvariable=self.gain_var, width=6,
                           command=self._edit_gain)
        gain.grid(row=6, column=1, sticky='w', pady=(8, 0))
        gain.bind('<FocusOut>', lambda e: self._edit_gain())
        self.info_label = ttk.Label(right, text='', foreground='#555', wraplength=self.px(440))
        self.info_label.grid(row=7, column=0, columnspan=4, sticky='w', pady=(8, 0))
        right.columnconfigure(3, weight=1)
        self.wave = Waveform(right, self._dragged, height=self.px(150))
        self.wave.grid(row=8, column=0, columnspan=4, sticky='nsew', pady=(8, 0))
        right.rowconfigure(8, weight=1)

        bottom = ttk.Frame(self, padding=(10, 4))
        bottom.pack(fill='x')
        ttk.Button(bottom, text='New', command=self.new_pack).pack(side='left')
        ttk.Button(bottom, text='Open pack...', command=self.open_pack).pack(side='left', padx=4)
        ttk.Button(bottom, text='Save pack', command=self.save_pack).pack(side='left')
        ttk.Button(bottom, text='Save as...', command=lambda: self.save_pack(ask=True)).pack(side='left', padx=4)
        self.uninstall_btn = ttk.Button(bottom, text='Uninstall', command=self.uninstall)
        self.uninstall_btn.pack(side='right')
        self.install_btn = ttk.Button(bottom, text='Install into the game', command=self.install)
        self.install_btn.pack(side='right', padx=4)
        self.export_btn = ttk.Button(bottom, text='Save DLC file...', command=self.export)
        self.export_btn.pack(side='right')
        self.install_file_btn = ttk.Button(bottom, text='Install a DLC file...', command=self.install_shared)
        self.install_file_btn.pack(side='right', padx=(0, 16))
        self.action_buttons = (self.uninstall_btn, self.install_btn, self.export_btn, self.install_file_btn)

        logf = ttk.LabelFrame(self, text='Log', padding=4)
        logf.pack(fill='both', expand=False, padx=10, pady=(4, 10))
        self.log = tk.Text(logf, height=8, wrap='word', font=('Consolas', 9), state='disabled')
        self.log.pack(fill='both', expand=True)
        self._select()

    # ------------------------------------------------------------ helpers --
    def write_log(self, text):
        self.log.configure(state='normal')
        self.log.insert('end', text)
        self.log.see('end')
        self.log.configure(state='disabled')

    def _first_free(self):
        used = mp.installed_packages(getattr(self, 'game', None))
        for n in list(range(18, 28)) + list(range(30, 64)):
            if n not in used:
                return n
        return 18

    def _package(self):
        try:
            n = int(self.pkg_var.get())
        except ValueError:
            return None
        return n if 1 <= n <= 63 else None

    def _update_package_status(self):
        n = self._package()
        if n is None:
            self.pkg_status.configure(text='Choose a number from 1 to 63', foreground='#b03a2e')
            return
        state = mp.installed_state(n, self.game)
        if n in OFFICIAL:
            text, color = f'In use: {OFFICIAL[n]}. Pick another number.', '#b03a2e'
        elif state:
            text, color = 'A music pack is installed here; installing replaces it.', '#b9770e'
        elif n in mp.installed_packages(self.game):
            text, color = 'In use by another installed DLC. Pick another number.', '#b03a2e'
        else:
            text, color = 'Free', '#1e8449'
        self.pkg_status.configure(text=text, foreground=color)

    def _loop_text(self, t):
        if 'xwb' in t:
            return 'from the bank'
        loop = t.get('loop', 'auto')
        if loop == 'whole':
            return 'whole file'
        if isinstance(loop, dict):
            return f'{fmt_time(loop["start"])} - {fmt_time(loop["end"])}'
        return 'finding...' if t.get('_status') == 'finding loop' else 'automatic'

    def _refresh_row(self, i):
        t = self.tracks[i]
        iid = str(i)
        status = t.get('_status', '')
        loop = t.get('loop')
        if status == 'ready' and 'xwb' not in t and '_dur' in t and (isinstance(loop, dict) or loop == 'whole'):
            end = loop['end'] if isinstance(loop, dict) else t['_dur']
            rate, ch, size, over = mp.track_format(end, self._quality())
            status = f'too big ({size / 2**20:.1f} MB)' if over else f'{rate // 100 / 10:g} kHz {"mono" if ch == 1 else ""}'.strip()
        values = (t.get('title', ''), self._loop_text(t), status)
        if self.tree.exists(iid):
            self.tree.item(iid, values=values)
        else:
            self.tree.insert('', 'end', iid=iid, values=values)

    def _refresh_list(self, select=None):
        self.tree.delete(*self.tree.get_children())
        for i in range(len(self.tracks)):
            self._refresh_row(i)
        if select is not None and 0 <= select < len(self.tracks):
            self.tree.selection_set(str(select))
            self.tree.see(str(select))
        self._select()

    def _current(self):
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    # ------------------------------------------------------------ tracks --
    def add_files(self):
        files = filedialog.askopenfilenames(
            title='Add songs', filetypes=[('Audio or wave banks', ' '.join('*' + e for e in mp.AUDIO_EXT) + ' *.xwb'),
                                          ('All files', '*.*')])
        for f in files:
            p = Path(f)
            if p.suffix.lower() == '.xwb':
                t = {'xwb': str(p), 'title': p.stem, '_status': 'ready'}
            else:
                title = None
                try:
                    import soundfile as sf
                    title = sf.SoundFile(str(p)).copy_metadata().get('title')
                except Exception:
                    pass
                import re
                t = {'file': str(p), 'title': title or re.sub(r'^\d+[\s._-]*', '', p.stem),
                     'loop': 'auto', '_status': 'finding loop'}
            self.tracks.append(t)
            i = len(self.tracks) - 1
            self._refresh_row(i)
            self._analyse(i, detect='xwb' not in t)
        if files:
            self._refresh_list(select=len(self.tracks) - 1)

    def remove(self):
        i = self._current()
        if i is None:
            return
        del self.tracks[i]
        self._refresh_list(select=min(i, len(self.tracks) - 1))

    def move(self, d):
        i = self._current()
        if i is None or not 0 <= i + d < len(self.tracks):
            return
        self.tracks[i], self.tracks[i + d] = self.tracks[i + d], self.tracks[i]
        self._refresh_list(select=i + d)

    def _analyse(self, i, detect):
        """Load the waveform (and find the loop) in the background."""
        t = self.tracks[i]

        def work():
            try:
                if 'xwb' in t:
                    self.q.put(('info', t, self._xwb_info(t)))
                    return
                data, rate = mp.load_audio(Path(t['file']))
                mono = data.mean(1)
                n = len(mono) // ENV_BINS * ENV_BINS or len(mono)
                bins = mono[:n].reshape(ENV_BINS, -1) if n >= ENV_BINS else mono[:, None]
                env = (bins.min(1), bins.max(1))
                self.q.put(('env', t, env, len(data) / rate))
                if detect:
                    found = mp.find_loop(data, rate)
                    self.q.put(('loop', t, found, rate))
            except Exception as err:  # shown in the list and the log
                self.q.put(('fail', t, f'{Path(t["file"]).name}: {err}'))

        threading.Thread(target=work, daemon=True).start()

    def _xwb_info(self, t):
        import struct
        b = Path(t['xwb']).read_bytes()[:4096]
        if b[:4] != b'DNBW':
            return 'Not an Xbox 360 wave bank (it must start with DNBW).'
        segs = struct.unpack_from('>10I', b, 12)
        count = struct.unpack_from('>I', b, 56)[0]
        dur, fmt, off, size, ls, ll = struct.unpack_from('>6I', b, segs[2])
        rate = (fmt >> 5) & 0x3FFFF or 1
        kind = {0: 'PCM', 1: 'XMA', 2: 'ADPCM', 3: 'WMA'}[fmt & 3]
        mb = Path(t['xwb']).stat().st_size / 2**20
        loop = f'loop {fmt_time(ls / rate)} - {fmt_time((ls + ll) / rate)}' if ll else 'no loop (plays once)'
        return (f'Ready-made {kind} wave bank, {count} wave(s), {rate} Hz, {fmt_time((dur >> 4) / rate)}, '
                f'{loop}, {mb:.2f} MB. Used as it is; only its name is changed.')

    def _select(self):
        i = self._current()
        self.selected = i
        state = 'normal' if i is not None else 'disabled'
        for w in (self.title_entry,):
            w.configure(state=state)
        if i is None:
            self.file_label.configure(text='Add songs with "Add songs...". Audio files (FLAC, WAV, OGG, MP3) '
                                           'or ready-made .xwb wave banks.')
            self._loading = True
            self.title_var.set('')
            self._loading = False
            self.info_label.configure(text='')
            self.wave.show(None, 0, None, None, 'Select a song')
            for w in (self.start_entry, self.end_entry, self.detect_btn, self.preview_btn, *self.mode_buttons):
                w.configure(state='disabled')
            return
        t = self.tracks[i]
        self._loading = True
        self.file_label.configure(text=t.get('file') if 'file' in t else t['xwb'])
        self.title_var.set(t.get('title', ''))
        self.gain_var.set(str(t.get('gain_db', 0)))
        loop = t.get('loop', 'auto')
        self.mode_var.set('whole' if loop == 'whole' else 'manual')
        if isinstance(loop, dict):
            self.start_var.set(fmt_time(loop['start']))
            self.end_var.set(fmt_time(loop['end']))
        else:
            self.start_var.set('')
            self.end_var.set('')
        self._loading = False
        bank = 'xwb' in t
        audio_state = 'disabled' if bank else 'normal'
        for w in (self.detect_btn, self.preview_btn, *self.mode_buttons):
            w.configure(state=audio_state)
        times_state = 'normal' if not bank and loop != 'whole' else 'disabled'
        self.start_entry.configure(state=times_state)
        self.end_entry.configure(state=times_state)
        self.info_label.configure(text=t.get('_info', ''))
        self._show_wave(t)

    def _show_wave(self, t):
        if 'xwb' in t:
            self.wave.show(None, 0, None, None, 'Ready-made wave bank: its own loop is used')
            return
        if '_env' not in t:
            self.wave.show(None, 0, None, None, 'Loading waveform...')
            return
        loop = t.get('loop')
        if loop == 'whole':
            s, e = 0.0, t['_dur']
        elif isinstance(loop, dict):
            s, e = loop['start'], loop['end']
        else:
            s = e = None
        self.wave.show(t['_env'], t['_dur'], s, e, t.get('_seam', ''))
        self.info_label.configure(text=self._format_text(t))

    def _quality(self):
        rate = self.rate_var.get()
        return {'sample_rate': 'auto' if rate == RATE_AUTO else int(rate.split()[0]),
                'mono': self.mono_var.get(), 'max_mb': self._max_mb()}

    def _format_text(self, t):
        """What the game gets: the part kept, the rate and the size."""
        if '_dur' not in t:
            return ''
        loop = t.get('loop')
        if isinstance(loop, dict):
            s, e = loop['start'], loop['end']
        elif loop == 'whole':
            s, e = 0.0, t['_dur']
        else:
            return 'Finding the loop...'
        q = self._quality()
        rate, ch, size, over = mp.track_format(e, q)
        cut = t['_dur'] - e
        text = (f'In game: {fmt_time(e)} kept of {fmt_time(t["_dur"])}'
                + (f' ({fmt_time(cut)} after the loop end is dropped)' if cut > 0.05 else '')
                + f', {rate} Hz {"stereo" if ch == 2 else "mono"}, {size / 2**20:.2f} MB.')
        if over:
            text += (f' Over the {q["max_mb"]:g} MB limit: the game may skip this song '
                     '(listed but silent).')
        elif q['sample_rate'] == 'auto' and rate < mp.RATE:
            text += (f' {mp.RATE} Hz would need {mp.track_format(e, {**q, "sample_rate": mp.RATE})[2] / 2**20:.1f} MB.')
        return text

    def _quality_changed(self):
        if getattr(self, 'selected', None) is not None and self.selected < len(self.tracks):
            t = self.tracks[self.selected]
            if 'xwb' not in t:
                self.info_label.configure(text=self._format_text(t))
        for i in range(len(getattr(self, 'tracks', []))):
            self._refresh_row(i)

    def _edit_title(self):
        if getattr(self, '_loading', False) or self.selected is None:
            return
        self.tracks[self.selected]['title'] = self.title_var.get()
        self._refresh_row(self.selected)

    def _edit_mode(self):
        i = self.selected
        if i is None:
            return
        t = self.tracks[i]
        if self.mode_var.get() == 'whole':
            if isinstance(t.get('loop'), dict):
                t['_manual'] = t['loop']
            t['loop'] = 'whole'
        else:
            t['loop'] = t.get('_manual', 'auto')
        self._refresh_row(i)
        self._select()

    def _edit_times(self):
        i = self.selected
        if i is None or getattr(self, '_loading', False):
            return
        t = self.tracks[i]
        if 'xwb' in t or t.get('loop') == 'whole':
            return
        try:
            s, e = parse_time(self.start_var.get()), parse_time(self.end_var.get())
        except ValueError:
            return
        old = t.get('loop') if isinstance(t.get('loop'), dict) else {}
        # Keep the detector's exact values unless the shown time was changed.
        if old and fmt_time(old['start']) == fmt_time(s) and fmt_time(old['end']) == fmt_time(e):
            return
        dur = t.get('_dur', e)
        if not 0 <= s < e <= dur + 1e-6:
            messagebox.showwarning('Loop points', f'The loop must satisfy 0 <= start < end <= {fmt_time(dur)}.')
            return
        t['loop'] = {'start': s, 'end': e}
        t['_seam'] = 'set by hand'
        self._refresh_row(i)
        self._show_wave(t)

    def _dragged(self, s, e):
        i = self.selected
        if i is None:
            return
        t = self.tracks[i]
        t['loop'] = {'start': s, 'end': e}  # the marker not dragged keeps its exact value
        t['_seam'] = 'set by hand'
        self._loading = True
        self.start_var.set(fmt_time(t['loop']['start']))
        self.end_var.set(fmt_time(t['loop']['end']))
        self._loading = False
        self._refresh_row(i)
        self._show_wave(t)

    def _edit_gain(self):
        if self.selected is None or getattr(self, '_loading', False):
            return
        try:
            g = float(self.gain_var.get())
        except ValueError:
            return
        t = self.tracks[self.selected]
        if g:
            t['gain_db'] = g
        else:
            t.pop('gain_db', None)

    def detect(self):
        i = self.selected
        if i is None or 'xwb' in self.tracks[i]:
            return
        t = self.tracks[i]
        t['loop'] = 'auto'
        t['_status'] = 'finding loop'
        self._refresh_row(i)
        self._select()
        self._analyse(i, detect=True)

    # ------------------------------------------------------------ preview --
    def preview(self):
        i = self.selected
        if i is None or self.busy:
            return
        t = dict(self.tracks[i])
        if t.get('loop', 'auto') == 'auto':
            messagebox.showinfo('Loop seam', 'The loop is still being found. Try again in a moment.')
            return
        t['_path'] = Path(t['file'])
        t.update(self._quality())
        t['auto_volume'] = self.auto_var.get()
        self.write_log(f'Preparing the loop seam of "{t["title"]}" at in-game quality...\n')

        def work():
            try:
                report = []
                audio, ls, ll, rate, ch = mp.prepare_track(t, report)
                path = Path(tempfile.gettempdir()) / 'hod_musicpack_seam.wav'
                mp.seam_preview(audio, ls, ll, rate, path)
                self.q.put(('play', str(path), report[-1]))
            except Exception as err:
                self.q.put(('log', f'Preview failed: {err}\n'))

        threading.Thread(target=work, daemon=True).start()

    def stop_sound(self):
        try:
            import winsound
            winsound.PlaySound(None, 0)
        except ImportError:
            pass

    # ------------------------------------------------------------ packs --
    def _max_mb(self):
        try:
            return max(1.0, float(self.mb_var.get()))
        except ValueError:
            return mp.DEFAULT_MAX_MB

    def pack_dict(self):
        mb = self._max_mb()
        tracks = []
        for t in self.tracks:
            clean = {k: v for k, v in t.items() if not k.startswith('_')}
            if mb != mp.DEFAULT_MAX_MB:
                clean['max_mb'] = mb
            else:
                clean.pop('max_mb', None)
            tracks.append(clean)
        q = self._quality()
        return {**self.extra, 'name': self.name_var.get().strip() or 'Music Pack',
                'package': self._package(), 'match_game_volume': self.auto_var.get(),
                'sample_rate': q['sample_rate'], 'mono': q['mono'], 'tracks': tracks}

    def _packs_dir(self):
        try:
            mp.PACKS.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        return mp.PACKS

    def new_pack(self):
        if self.tracks and not messagebox.askyesno('New pack', 'Start a new pack? Unsaved changes are lost.'):
            return
        self.tracks, self.pack_path, self.extra = [], None, {}
        self.auto_var.set(True)
        self.rate_var.set(RATE_AUTO)
        self.mono_var.set(False)
        self.name_var.set('My Music Pack')
        self.pkg_var.set(str(self._first_free()))
        self._update_package_status()
        self._refresh_list()

    def open_pack(self):
        f = filedialog.askopenfilename(title='Open pack', initialdir=str(self._packs_dir()),
                                       filetypes=[('Pack files', '*.json')])
        if not f:
            return
        try:
            pack = json.loads(Path(f).read_text(encoding='utf-8'))
        except (OSError, ValueError) as err:
            messagebox.showerror('Open pack', str(err))
            return
        base = Path(f).parent
        self.pack_path = Path(f)
        self.extra = {k: v for k, v in pack.items() if k not in ('name', 'package', 'tracks', 'match_game_volume',
                                                             'sample_rate', 'mono')}
        self.auto_var.set(bool(pack.get('match_game_volume', True)))
        rate = pack.get('sample_rate', 'auto')
        self.rate_var.set(f'{rate} Hz' if rate in FIXED_RATES else RATE_AUTO)
        self.mono_var.set(bool(pack.get('mono', False)))
        self.name_var.set(pack.get('name', Path(f).stem))
        self.pkg_var.set(str(pack.get('package') or self._first_free()))
        self.tracks = []
        mbs = set()
        for t in pack.get('tracks', []):
            t = dict(t)
            for key in ('file', 'xwb'):
                if key in t and not Path(t[key]).is_absolute():
                    t[key] = str(base / t[key])
            if 'max_mb' in t:
                mbs.add(t['max_mb'])
            t['_status'] = 'ready' if 'xwb' in t or isinstance(t.get('loop'), dict) or t.get('loop') == 'whole' \
                else 'finding loop'
            self.tracks.append(t)
        self.mb_var.set(str(mbs.pop() if len(mbs) == 1 else mp.DEFAULT_MAX_MB))
        for i, t in enumerate(self.tracks):
            self._analyse(i, detect=t.get('loop', 'auto') == 'auto' and 'xwb' not in t)
        self._update_package_status()
        self._refresh_list(select=0)
        self.title(f'HoD Music Pack Builder - {self.pack_path.name}')

    def save_pack(self, ask=False):
        if self._package() is None:
            messagebox.showerror('Save pack', 'Choose a DLC package number from 1 to 63.')
            return False
        if ask or self.pack_path is None:
            f = filedialog.asksaveasfilename(title='Save pack', defaultextension='.json',
                                             initialdir=str(self._packs_dir()),
                                             initialfile=(self.name_var.get().strip() or 'music_pack')
                                             .lower().replace(' ', '_') + '.json',
                                             filetypes=[('Pack files', '*.json')])
            if not f:
                return False
            self.pack_path = Path(f)
        self.pack_path.parent.mkdir(parents=True, exist_ok=True)
        self.pack_path.write_text(json.dumps(self.pack_dict(), indent=2, ensure_ascii=False) + '\n',
                                  encoding='utf-8')
        self.title(f'HoD Music Pack Builder - {self.pack_path.name}')
        self.write_log(f'Saved {self.pack_path}\n')
        return True

    def _check_ready(self, need_tracks=True):
        if self.busy:
            return False
        if need_tracks and not self.tracks:
            messagebox.showerror('Music pack', 'Add at least one song.')
            return False
        n = self._package()
        if n is None:
            messagebox.showerror('Music pack', 'Choose a DLC package number from 1 to 63.')
            return False
        if n in OFFICIAL or (n in mp.installed_packages(self.game) and not mp.installed_state(n, self.game)):
            messagebox.showerror('Music pack', f'Package {n} is used by other DLC. Pick another number.')
            return False
        for t in self.tracks:
            if not t.get('title', '').strip():
                messagebox.showerror('Music pack', 'Every song needs a title.')
                return False
            if t.get('loop', 'auto') == 'auto' and 'xwb' not in t and t.get('_status') == 'finding loop':
                if not messagebox.askyesno('Music pack', 'Some loops are still being found. The build will '
                                                         'find them itself (slower). Continue?'):
                    return False
                break
        return self.save_pack()

    def _run(self, label, fn):
        self.busy = True
        for b in self.action_buttons:
            b.configure(state='disabled')
        self.write_log(f'--- {label} ---\n')

        def work():
            try:
                with contextlib.redirect_stdout(QueueWriter(self.q)):
                    fn()
                self.q.put(('done', label, None))
            except Exception as err:
                self.q.put(('log', traceback.format_exc() if not isinstance(err, (AssertionError, RuntimeError))
                            else f'{err}\n'))
                self.q.put(('done', label, str(err) or type(err).__name__))

        threading.Thread(target=work, daemon=True).start()

    def _need_game(self, action):
        if mp.game_running():
            messagebox.showerror(action, 'Close Harmony of Despair first.')
            return False
        if not self.game:
            self.choose_game()
        return bool(self.game)

    def export(self):
        """Build the pack and save it as one DLC file, like the official packs."""
        if not self._check_ready():
            return
        n = self._package()
        dest = filedialog.asksaveasfilename(
            title='Save the music pack as one DLC file', initialdir=str(self._packs_dir()),
            initialfile=mp.content_id(n),
            filetypes=[('Xbox 360 DLC package (no extension)', '*'), ('All files', '*.*')])
        if not dest:
            return
        dest, path = Path(dest), self.pack_path

        def work():
            out_dir, package, pid = mp.build(path)
            shutil.copyfile(mp.package_file_of(out_dir, pid), dest)
            print(f'Saved {dest}')
            print('Share this one file. To install it: "Install a DLC file..." in this tool, or put it in the '
                  'DLC folder you give the HarmonyRecomp setup and run the setup again.')
        self._run('Save DLC file', work)

    def install(self):
        if not self._check_ready() or not self._need_game('Install'):
            return
        path, game = self.pack_path, self.game
        self._run('Install', lambda: mp.install(path, game))

    def install_shared(self):
        """Install a single-file music pack someone else made."""
        if self.busy or not self._need_game('Install a DLC file'):
            return
        f = filedialog.askopenfilename(title='Music pack DLC file', initialdir=str(self._packs_dir()),
                                       filetypes=[('All files', '*.*')])
        if not f:
            return
        game = self.game

        def work():
            mp.install_file(Path(f), game)
        self._run('Install', work)

    def uninstall(self):
        n = self._package()
        if n is None or self.busy:
            return
        if not mp.installed_state(n, self.game):
            messagebox.showinfo('Uninstall', f'No music pack is installed as package {n}.')
            return
        if not self._need_game('Uninstall'):
            return
        if not messagebox.askyesno('Uninstall', f'Remove music pack {n} from the game?'):
            return
        game = self.game
        self._run('Uninstall', lambda: mp.uninstall_package(n, game))

    # ------------------------------------------------------------ events --
    def _poll(self):
        try:
            while True:
                msg = self.q.get_nowait()
                kind = msg[0]
                if kind == 'log':
                    self.write_log(msg[1])
                elif kind in ('env', 'loop', 'fail', 'info'):
                    t = msg[1]
                    if t not in self.tracks:
                        continue
                    i = self.tracks.index(t)
                    if kind == 'env':
                        t['_env'], t['_dur'] = msg[2], msg[3]
                        if t.get('loop', 'auto') != 'auto':
                            t['_status'] = 'ready'
                    elif kind == 'info':
                        t['_info'] = msg[2]
                        t['_status'] = 'ready' if msg[2].startswith('Ready') else 'not usable'
                    elif kind == 'fail':
                        t['_status'] = 'error'
                        self.write_log(msg[2] + '\n')
                    else:
                        found, rate = msg[2], msg[3]
                        if t.get('loop', 'auto') != 'auto':
                            continue  # set by hand while the search ran: keep it
                        if found is None:
                            t['loop'] = 'whole'
                            t['_seam'] = 'no repeat found: whole file loops'
                            self.write_log(f'{t["title"]}: no repeat found; set the loop by hand '
                                           'or keep "whole file".\n')
                        else:
                            s, e, seam, _ = found
                            t['loop'] = {'start': s / rate, 'end': e / rate}
                            t['_seam'] = f'found automatically (match {10 * np.log10(max(seam, 1e-9)):.0f} dB)'
                        t['_status'] = 'ready'
                    self._refresh_row(i)
                    if i == self.selected:
                        self._select()
                elif kind == 'play':
                    r = msg[2]
                    self.write_log(f'Playing the seam: last 4 s before the loop end, then the loop start. '
                                   f'In game: {r["rate"]} Hz {"stereo" if r["channels"] == 2 else "mono"}, '
                                   f'{r["seconds"]:.1f} s kept, volume {r["gain_db"]:+.1f} dB '
                                   f'({r["loudness_lufs"]:.1f} LUFS).\n')
                    try:
                        import winsound
                        winsound.PlaySound(msg[1], winsound.SND_FILENAME | winsound.SND_ASYNC)
                    except ImportError:
                        import os
                        os.startfile(msg[1])
                elif kind == 'done':
                    self.busy = False
                    for b in self.action_buttons:
                        b.configure(state='normal')
                    self._update_package_status()
                    if msg[2]:
                        messagebox.showerror(msg[1], msg[2])
                    elif msg[1] == 'Install':
                        messagebox.showinfo('Install', 'Installed. Start the game: HarmonyRecomp adds the pack '
                                                       'as it starts, and the songs are in the track list.')
        except queue.Empty:
            pass
        self.after(100, self._poll)


def selftest(pack, out_dir):
    """Hidden check for the bundled exe: build a pack without the window.

    "HoD Music Pack Builder.exe" --selftest pack.json OUTDIR  (log: OUTDIR/selftest.log)
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / 'selftest.log', 'w', encoding='utf-8') as log, \
            contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        try:
            print('frozen', mp.FROZEN, 'python', sys.version.split()[0], 'packs', mp.PACKS)
            mp.build(pack, out_dir / 'build')
            print('SELFTEST OK')
        except Exception:
            traceback.print_exc()
            print('SELFTEST FAILED')


def main():
    if len(sys.argv) == 4 and sys.argv[1] == '--selftest' and not MISSING:
        selftest(sys.argv[2], sys.argv[3])
        return
    if MISSING:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror('HoD Music Pack Builder',
                             'Missing Python packages: ' + ', '.join(MISSING) +
                             '\n\nInstall them with:\npython -m pip install ' + ' '.join(MISSING))
        return
    App().mainloop()


if __name__ == '__main__':
    main()
